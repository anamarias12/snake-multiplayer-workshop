# config.py
HOST = '127.0.0.1'
PORT = 65432
LOGIN_KEY = '1234'
FPS = 4
GAME_SIZE = (20, 15)  # width, height
SNAKE_LEN = 4
WIN_SCORE = 100

# Message IDs
MSG_LOGIN = 'login'
MSG_LOGIN_RESP = 'login_resp'
MSG_START = 'start'
MSG_INPUT = 'input'
MSG_UPDATE = 'update'
MSG_PING = 'ping'
MSG_PONG = 'pong'
MSG_DISCONNECT = 'disconnect'

# Directions
DIRS = {'UP': (0, -1), 'DOWN': (0, 1), 'LEFT': (-1, 0), 'RIGHT': (1, 0)}
