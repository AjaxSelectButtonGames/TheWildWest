import json
from protocol import PacketType
from packet_factory import PacketFactory

class PacketHandler:
    def __init__(self, server):
        self.server = server

    async def process_packet(self, message, address, writer=None):
        try:
            packet = json.loads(message)
            packet_type = packet.get("id")
            data = packet.get("data", {})

            if packet_type == PacketType.PING:
                print(f"[PING] From {address}")
                pong = PacketFactory.build(PacketType.PONG, {"msg": "PONG"})
                return pong

            elif packet_type == PacketType.PLAYER_JOIN:
                join_data = json.loads(packet["data"])
                preferred_id = join_data.get("preferredId")
                
                if preferred_id and preferred_id not in self.server.world_state.players:
                    assigned_id = preferred_id
                else:
                    import uuid
                    assigned_id = str(uuid.uuid4())
                self.server.client_players[writer] = assigned_id
                
                confirm_packet = PacketFactory.build(PacketType.PLAYER_ID_ASSIGNED, {
                    "assignedId": assigned_id
                })
                
                writer.write((confirm_packet + "\n").encode())
                await writer.drain()
                
                print(f"[JOIN] Assigned player ID {assigned_id} to {address}")

            elif packet_type == PacketType.CHAT:
                msg = data.get("msg", "")
                print(f"[CHAT] {address}: {msg}")
                # (optional) broadcast chat later
                return None

            elif packet_type == PacketType.PLAYER_MOVE:
                # Player sends movement update
                pid = self.server.client_players.get(writer)
                if pid:
                    x, y, z = data.get("x", 0), data.get("y", 0), data.get("z", 0)
                    self.server.world_state.update_position(pid, x, y, z)
                    print(f"[MOVE] {pid} -> ({x}, {y}, {z})")
                return None

            else:
                print(f"[WARN] Unknown packet: {packet}")
                return None

        except Exception as e:
            print(f"[ERROR] Failed to process packet from {address}: {e}")
            return None
