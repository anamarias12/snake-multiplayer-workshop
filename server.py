import socket
import threading
import time
import random
import json
from config import HOST, PORT, LOGIN_KEY, FPS, GAME_SIZE, SNAKE_LEN, WIN_SCORE, MSG_LOGIN, MSG_LOGIN_RESP, MSG_START, MSG_INPUT, MSG_UPDATE, MSG_PING, MSG_PONG, MSG_DISCONNECT, DIRS

class Snake:
    def __init__(self, start_pos, direction):
        self.body = [start_pos]
        self.direction = direction
        for _ in range(SNAKE_LEN-1):
            x, y = self.body[-1]
            dx, dy = DIRS[direction]
            self.body.append((x-dx, y-dy))
        self.score = 0
        self.alive = True
        self.last_input = direction

    def move(self, direction=None):
        if direction:
            self.last_input = direction
        dx, dy = DIRS[self.last_input]
        head = (self.body[0][0]+dx, self.body[0][1]+dy)
        self.body = [head] + self.body[:-1]

    def check_collision(self, game_size):
        x, y = self.body[0]
        if x < 0 or x >= game_size[0] or y < 0 or y >= game_size[1]:
            self.alive = False

    def eat(self, fruit):
        if self.body[0] == fruit:
            self.score += 10
            return True
        return False

class GameServer:
    def __init__(self):
        self.clients = {}
        self.snakes = {}
        self.player_numbers = {}
        self.next_player_num = 1
        self.fruit = None
        self.lock = threading.Lock()
        self.running = True
        self.last_ping = {}

    def spawn_fruit(self):
        while True:
            pos = (random.randint(0, GAME_SIZE[0]-1), random.randint(0, GAME_SIZE[1]-1))
            if all(pos not in snake.body for snake in self.snakes.values()):
                return pos

    def handle_client(self, conn, addr):
        client_id = addr[1]
        buffer = ''
        logged_in = False
        try:
            while self.running:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data.decode()
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)

                    if msg['id'] == MSG_LOGIN:
                        if msg['key'] == LOGIN_KEY:
                            print(f"Login success for client {client_id}")
                            conn.send((json.dumps({'id': MSG_LOGIN_RESP, 'ok': True}) + '\n').encode())
                            with self.lock:
                                self.clients[client_id] = conn
                                # all snakes start from upper left corner
                                self.player_numbers[client_id] = self.next_player_num
                                self.next_player_num += 1
                                self.snakes[client_id] = Snake((2, 2), 'RIGHT')
                                self.last_ping[client_id] = time.time()
                                if not self.fruit:
                                    self.fruit = self.spawn_fruit()
                            logged_in = True
                        else:
                            print(f"Login failed for client {client_id}")
                            conn.send((json.dumps({'id': MSG_LOGIN_RESP, 'ok': False}) + '\n').encode())
                            return
                    elif not logged_in:
                        continue
                    elif msg['id'] == MSG_START:
                        print(f"Game started")
                    elif msg['id'] == MSG_INPUT:
                        with self.lock:
                            if client_id in self.snakes and self.snakes[client_id].alive:
                                # prevent 180-degree turns
                                desired = msg['dir']
                                cur = self.snakes[client_id].last_input
                                opposites = {('UP','DOWN'),('DOWN','UP'),('LEFT','RIGHT'),('RIGHT','LEFT')}
                                if (cur, desired) not in opposites:
                                    self.snakes[client_id].last_input = desired
                    elif msg['id'] == MSG_PING:
                        self.last_ping[client_id] = time.time()
                        conn.send((json.dumps({'id': MSG_PONG}) + '\n').encode())
        except Exception as e:
            print(f"Client {client_id} error: {e}")
        finally:
            with self.lock:
                if client_id in self.snakes:
                    del self.snakes[client_id]
                if client_id in self.clients:
                    del self.clients[client_id]
                if client_id in self.last_ping:
                    del self.last_ping[client_id]
                if client_id in self.player_numbers:
                    del self.player_numbers[client_id]
            conn.close()

    def broadcast(self, msg):
        for conn in list(self.clients.values()):
            try:
                conn.send((json.dumps(msg) + '\n').encode())
            except:
                pass

    def update(self):
        with self.lock:
            # move and collisions
            for cid, snake in list(self.snakes.items()):
                if snake.alive:
                    snake.move()
                    snake.check_collision(GAME_SIZE)
                    if not snake.alive:
                        self.broadcast({'id': 'lose', 'cid': cid})
                        continue
                    if snake.eat(self.fruit):
                        if snake.score >= WIN_SCORE:
                            self.broadcast({'id': 'win', 'cid': cid})
                            self.running = False
                        self.fruit = self.spawn_fruit()

            # head-on collisions
            positions = {}
            for cid, snake in self.snakes.items():
                if snake.alive:
                    positions.setdefault(tuple(snake.body[0]), []).append(cid)
            for pos, cids in positions.items():
                if len(cids) > 1:
                    for cid in cids:
                        self.snakes[cid].alive = False
                        self.broadcast({'id': 'lose', 'cid': cid})

            # disconnect
            now = time.time()
            for cid in list(self.last_ping.keys()):
                if now - self.last_ping[cid] > 5:
                    self.broadcast({'id': MSG_DISCONNECT, 'cid': cid})
                    if cid in self.clients:
                        try:
                            self.clients[cid].close()
                        except:
                            pass
                        del self.clients[cid]
                    if cid in self.snakes:
                        del self.snakes[cid]
                    del self.last_ping[cid]

            # send world state
            self.broadcast({
                'id': MSG_UPDATE,
                'snakes': {cid: snake.body for cid, snake in self.snakes.items()},
                'fruit': self.fruit,
                'scores': {cid: snake.score for cid, snake in self.snakes.items()},
                'players': self.player_numbers
            })

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(8)
        print(f"Server listening on {HOST}:{PORT}")
        threading.Thread(target=self.game_loop, daemon=True).start()
        while self.running:
            conn, addr = s.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

    def game_loop(self):
        while self.running:
            self.update()
            time.sleep(1/FPS)

if __name__ == '__main__':
    GameServer().run()