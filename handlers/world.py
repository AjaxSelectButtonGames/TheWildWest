import json
from protocol import PacketType


async def broadcast_world_state(server):
    players = [
        {"id": pid, "x": pos[0], "y": pos[1], "z": pos[2]}
        for pid, pos in server.client_positions.items()
    ]
    packet = json.dumps({
        "id": PacketType.WORLD_UPDATE,
        "data": {"players": players}
    }) + "\n"

    print(f"[BROADCAST] {len(players)} players")

    dead_clients = []
    for w in list(server.clients.keys()):
        try:
            w.write(packet.encode())
            await w.drain()
        except Exception as e:
            print(f"[ERROR] Broadcast to client failed: {e}")
            dead_clients.append(w)

    for w in dead_clients:
        player_id = server.clients.pop(w, None)
        if player_id and player_id in server.client_positions:
            del server.client_positions[player_id]
            print(f"[CLEANUP] Removed dead client {player_id}")
