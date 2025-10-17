import json


async def broadcast_packet(server, packet_str: str):
    dead_clients = []
    for w in list(server.clients.keys()):
        try:
            w.write(packet_str.encode())
            await w.drain()
        except Exception as e:
            print(f"[ERROR] Failed to broadcast to client: {e}")
            dead_clients.append(w)

    for w in dead_clients:
        player_id = server.clients.pop(w, None)
        if player_id and player_id in server.client_positions:
            del server.client_positions[player_id]
            print(f"[CLEANUP] Removed dead client {player_id}")
