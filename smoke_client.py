import socket
import json
import time
from protocol import PacketType

s = socket.create_connection(('127.0.0.1', 5000))

def send_packet(p):
    s.send((json.dumps(p)+"\n").encode())
    time.sleep(0.05)

# PING
send_packet({"id": PacketType.PING, "data": {}})
# Join
send_packet({"id": PacketType.PLAYER_JOIN, "data": {}})
# Small move
send_packet({"id": PacketType.PLAYER_MOVE, "data": {"x": 10, "y": 0, "z": 10}})
# Chat
send_packet({"id": PacketType.CHAT, "data": {"text": "hello from client", "channel": "global"}})

# Read responses (non-blocking read)
s.settimeout(1.0)
try:
    while True:
        line = s.recv(4096)
        if not line:
            break
        print('CLIENT RECV:', line.decode().strip())
except Exception:
    pass

s.close()
print('client done')
