import socket
import threading
import time
import json
import pygame
import random
from config import HOST, PORT, LOGIN_KEY, FPS, GAME_SIZE, MSG_LOGIN, MSG_LOGIN_RESP, MSG_START, MSG_INPUT, MSG_UPDATE, MSG_PING, MSG_PONG, MSG_DISCONNECT, DIRS

CELL_SIZE = 32
DIR_KEYS = {pygame.K_UP: 'UP', pygame.K_DOWN: 'DOWN', pygame.K_LEFT: 'LEFT', pygame.K_RIGHT: 'RIGHT'}

NEON_COLORS = [
    (57,255,20),
    (0,255,255),
    (255,20,147),
    (255,255,0),
    (0,191,255),
]
SEGMENT_COLORS = [
    (0,200,0),
    (240,200,0),
    (0,120,255),
]

class SnakeClient:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.snakes = {}
        self.fruit = None
        self.scores = {}
        self.players = {}
        self.my_id = None
        self.running = True
        self.last_update = time.time()
        self.last_ping = time.time()
        self.predicted_dir = 'RIGHT'
        self.predicted_body = []
        self.instant_move = False
        self.simulate_lag = False
        self.lag_loss = 0.3
        self.ack_pending = False
        self.win_cid = None
        self.lose_cid = None

    def connect(self):
        self.sock.connect((HOST, PORT))
        try:
            key = input('LOGIN - Insert key: ')
        except:
            key = LOGIN_KEY
        self.sock.send((json.dumps({'id': MSG_LOGIN, 'key': key}) + '\n').encode())
        buffer = ''
        while True:
            data = self.sock.recv(1024)
            if not data:
                print('No response from server')
                return False
            buffer += data.decode()
            if '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                resp = json.loads(line)
                break
        if not resp.get('ok'):
            print('Login failed')
            self.sock.close()
            return False
        self.login_succeeded = True
        return True

    def send_input(self, direction):
        if self.simulate_lag and random.random() < self.lag_loss:
            self.ack_pending = True
            return
        self.sock.send((json.dumps({'id': MSG_INPUT, 'dir': direction}) + '\n').encode())
        self.ack_pending = False

    def ping(self):
        self.sock.send((json.dumps({'id': MSG_PING}) + '\n').encode())

    def recv_thread(self):
        buffer = ''
        while self.running:
            try:
                data = self.sock.recv(1024)
                if not data:
                    break
                buffer += data.decode()
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except Exception as e:
                        print('Error decoding:', e)
                        continue
                    if msg['id'] == MSG_UPDATE:
                        self.snakes = msg['snakes']
                        self.fruit = msg['fruit']
                        self.scores = msg['scores']
                        self.players = msg.get('players', {})
                        self.last_update = time.time()
                        if self.my_id and self.instant_move:
                            my_key = str(self.my_id)
                            if my_key in self.snakes:
                                self.predicted_body = self.snakes[my_key]
                    elif msg['id'] == MSG_PONG:
                        self.last_ping = time.time()
                    elif msg['id'] == MSG_DISCONNECT:
                        self.running = False
                        print('Disconnected by server')
                        break
                    elif msg['id'] == 'win':
                        self.win_cid = msg['cid']
                    elif msg['id'] == 'lose':
                        self.lose_cid = msg['cid']
            except Exception as e:
                print('Error:', e)
                break
        self.running = False

    # user interface
    def draw_neon_border(self, screen, t):
        w, h = screen.get_width(), screen.get_height()
        pad = 24
        color = NEON_COLORS[int(t*4)%len(NEON_COLORS)]
        for i in range(6):
            rect = pygame.Rect(pad-i*3, pad-i*3, w-2*(pad-i*3), h-2*(pad-i*3))
            pygame.draw.rect(screen, color, rect, 3, border_radius=16)

    def draw_center_text(self, screen, text, font, color, y):
        surf = font.render(text, True, color)
        screen.blit(surf, (screen.get_width()//2 - surf.get_width()//2, y))

    def run(self):
        if not self.connect():
            return
        threading.Thread(target=self.recv_thread, daemon=True).start()
        pygame.init()
        screen = pygame.display.set_mode((GAME_SIZE[0]*CELL_SIZE, GAME_SIZE[1]*CELL_SIZE))
        clock = pygame.time.Clock()
        self.my_id = self.sock.getsockname()[1]

        font_title = pygame.font.SysFont('Courier', 64, bold=True)
        font_menu = pygame.font.SysFont('Courier', 28, bold=True)
        font_hud = pygame.font.SysFont('Courier', 22, bold=True)

        # start screen
        started = False
        menu_index = 0
        start_options = ['Start Game', 'Exit']
        t0 = time.time()
        while not started:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); self.sock.close(); return
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        menu_index = (menu_index-1) % len(start_options)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_index = (menu_index+1) % len(start_options)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if start_options[menu_index] == 'Start Game':
                            if hasattr(self, 'login_succeeded') and self.login_succeeded:
                                self.sock.send((json.dumps({'id': MSG_START}) + '\n').encode())
                                started = True
                        else:
                            pygame.quit(); self.sock.close(); return

            screen.fill((5, 5, 25))
            self.draw_neon_border(screen, time.time()-t0)
            self.draw_center_text(screen, 'RETRO SNAKE', font_title, (0,255,180), 110)
            blink = int((time.time()-t0)*2) % 2
            if blink:
                self.draw_center_text(screen, 'Press ENTER to Start', font_menu, (255,255,0), 190)
            # options
            base_y = 260
            for i, opt in enumerate(start_options):
                c = (255,255,255) if i!=menu_index else (57,255,20)
                prefix = '▶ ' if i==menu_index else '  '
                self.draw_center_text(screen, prefix+opt, font_menu, c, base_y + i*40)
            pygame.display.flip()
            clock.tick(60)

        # main loop
        while self.running:
            # input
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in DIR_KEYS:
                        desired = DIR_KEYS[event.key]
                        if self.instant_move and self.predicted_body:
                            dx, dy = DIRS[desired]
                            head = (self.predicted_body[0][0]+dx, self.predicted_body[0][1]+dy)
                            self.predicted_body = [head] + self.predicted_body[:-1]
                        self.send_input(desired)
                    elif event.key == pygame.K_l:
                        self.simulate_lag = not self.simulate_lag
                        print('Lag simulation:', self.simulate_lag)
                    elif event.key == pygame.K_m:
                        self.instant_move = not self.instant_move
                        print('Client prediction:', self.instant_move)

            if time.time() - self.last_ping > 1:
                self.ping()
            if self.ack_pending:
                self.send_input(self.predicted_dir)

            # render
            screen.fill((5, 5, 25))

            # apple
            if self.fruit:
                fx, fy = self.fruit
                cx = fx*CELL_SIZE + CELL_SIZE//2
                cy = fy*CELL_SIZE + CELL_SIZE//2
                pygame.draw.circle(screen, (220,0,0), (cx, cy), CELL_SIZE//2 - 4)
                stem_rect = pygame.Rect(0,0,6,12)
                stem_rect.center = (cx, cy - CELL_SIZE//2 + 6)
                pygame.draw.rect(screen, (0,180,0), stem_rect, border_radius=3)

            # snakes colors
            for cid, body in self.snakes.items():
                cid_str = str(cid)
                is_me = cid_str == str(self.my_id)
                for idx, (x, y) in enumerate(body):
                    color = SEGMENT_COLORS[idx % len(SEGMENT_COLORS)]
                    rect = pygame.Rect(x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE)
                    pygame.draw.rect(screen, color, rect, border_radius=6)
                    if is_me and idx == 0:
                        pygame.draw.rect(screen, (255,255,255), rect.inflate(6,6), 2, border_radius=8)

            # predicted overlay
            if self.instant_move and self.predicted_body:
                for x, y in self.predicted_body:
                    pygame.draw.rect(screen, (255,255,0), (x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE), 2, border_radius=6)

            # points
            y = 6
            for cid, score in sorted(self.scores.items(), key=lambda kv: int(kv[0])):
                txt = f"Player {cid} points: {score}"
                surf = font_hud.render(txt, True, (255,255,255))
                screen.blit(surf, (6, y))
                y += 22

            # show other players info under HUD
            if self.players:
                y += 6
                surf = font_hud.render('Other players:', True, (200,200,200))
                screen.blit(surf, (6, y))
                y += 20
                for cid, meta in sorted(self.players.items(), key=lambda kv: int(kv[0])):
                    # skip self
                    if str(cid) == str(self.my_id):
                        continue
                    pscore = self.scores.get(str(cid), self.scores.get(cid, 0))
                    txt = f"{cid} — {pscore} pts"
                    surf = font_hud.render(txt, True, (220,220,220))
                    screen.blit(surf, (6, y))
                    y += 18

            pygame.display.flip()
            clock.tick(FPS)

            # check win/lose overlays
            if self.win_cid is not None or self.lose_cid == self.my_id:
                break

        # end screen
        # determine message
        you_won = (self.win_cid == self.my_id)
        you_lost = (self.lose_cid == self.my_id) or (not you_won and self.win_cid is not None)
        end_options = ['Exit']
        menu_index = 0
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); self.sock.close(); return
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        menu_index = (menu_index-1) % len(end_options)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        menu_index = (menu_index+1) % len(end_options)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        pygame.quit(); self.sock.close(); return

            screen.fill((5, 5, 25))
            self.draw_neon_border(screen, time.time()-t0)
            if you_won:
                self.draw_center_text(screen, 'YOU WIN!', font_title, (57,255,20), 140)
            elif you_lost:
                self.draw_center_text(screen, 'YOU LOSE!', font_title, (255,80,80), 140)
            else:
                self.draw_center_text(screen, 'EXIT?', font_title, (255,80,80), 140)
            base_y = 240
            for i, opt in enumerate(end_options):
                c = (255,255,255) if i!=menu_index else (255,255,0)
                prefix = '▶ ' if i==menu_index else '  '
                self.draw_center_text(screen, prefix+opt, font_menu, c, base_y + i*40)
            pygame.display.flip()
            clock.tick(60)

if __name__ == '__main__':
    SnakeClient().run()