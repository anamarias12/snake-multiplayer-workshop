# Multiplayer Snake Game

A retro-inspired multiplayer Snake game with client-server architecture.  
The server handles all the game logic, and clients can connect by logging in with a key.  

## Features

- Multiplayer gameplay (multiple clients can join).  
- Login system with key authentication.  
- Real-time updates between server and clients.  
- Neon retro-style UI with animations.  

## How to Run

Start the **server**:
python3 server.py
Then run one or more clients in separate terminals:
python3 client.py

## Requirements

Python 3.x
pygame library

## Controls

Arrow keys → Move snake
M → Toggle client prediction (instant move)
L → Toggle lag simulation
