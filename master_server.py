# master_server.py
import asyncio
import json
import uuid
import grpc
import time
import math
import threading 
import os
import hmac
import hashlib
from protocol import PacketType
from packets import parse_raw_packet
from generated import chatservice_pb2, chatservice_pb2_grpc
from chat import start_chat_server, ChatManager # ChatManager added
from handlers import player as player_handlers
from handlers import chat as chat_handlers
from handlers import world as world_handlers
from handlers import npc as npc_handlers
from NPCService import serve as npc_serve

class MasterServer:
    def __init__(self):
        self.clients = {}  # writer -> player_id
        self.client_positions = {}  # player_id -> (x, y, z)
        # New: Track last move time for velocity/speed check
        self.last_move_times = {} # player_id -> timestamp
        # writer registry for quick lookup: player_id -> writer
        self.writers_by_id = {}
        # nicknames
        self.nicknames = {}  # player_id -> nickname
        self.nickname_to_id = {}  # nickname -> player_id
        
        self.spawn_points = [
            (208.6597, 6.989525, 545.12),  # spawnpoint1
            (208.6597, 6.989525, 548)      # spawnpoint2
        ]

        # Chat integration
        self.chat_stub = None
        # Pass 'self' (the master_server) and None (for the chat_stub, to be set later)
        self.chat = ChatManager(self, None) 
        
        # World Sanity checks
        # Max speed in units/second. Set to a reasonable sprint speed.
        self.max_speed = 10.0 
        # Tweak these bounds to match your actual map boundaries
        self.world_bounds = {
            "min_x": 150,
            "max_x": 250,
            "min_z": 500,
            "max_z": 600,
            "min_y": 0,
            "max_y": 50,
        }
        
        self.heightmap = None
        self.colliders = []

        # Handshake state: writer -> nonce
        self.handshake_nonces = {}
        # Server secret for HMAC (in a real deployment store this securely)
        self.server_secret = "dev-secret-change-me"
        
    def get_height_at(self, x, z):
        """Placeholder for heightmap lookup."""
        # For the spawn area (around z=545), a height of 6.989525 seems right.
        # This function would normally use bilinear interpolation on your heightmap data.
        return 6.989525
    
    def is_inside_collider(self, x, y, z):
        """Placeholder for detailed collider check."""
        # This function would normally use 3D geometry tests (e.g., raycasting, point-in-mesh)
        return False
        
    
    async def init_chat_stub(self):
        """Create a gRPC channel to our local ChatService."""
        channel = grpc.aio.insecure_channel("127.0.0.1:6000")
        self.chat_stub = chatservice_pb2_grpc.ChatServiceStub(channel)
        self.chat.stub = self.chat_stub # Inject the stub into the ChatManager

        print("[CHAT] gRPC stub initialized")

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info("peername")
        print(f"[CONNECT] {addr}")

        # Issue handshake challenge (nonce) immediately on new connection
        nonce = os.urandom(16).hex()
        self.handshake_nonces[writer] = nonce
        await self.send(writer, PacketType.HANDSHAKE_CHALLENGE, {"nonce": nonce})

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                message = data.decode().strip()
                if not message:
                    continue

                print(f"[RECV] From {addr}: {message}")
                try:
                    packet_raw = json.loads(message)
                    packet = parse_raw_packet(packet_raw)
                    # pass either the object (preferred) or raw dict to keep compatibility
                    await self.handle_packet(packet, writer)
                except Exception as e:
                    print(f"[ERROR] Failed to process packet from {addr}: {e}")

        finally:
            # Cleanup on disconnect
            player_id = self.clients.get(writer)
            if player_id:
                print(f"[DISCONNECT] {addr}, player {player_id}")
                if player_id in self.client_positions:
                    del self.client_positions[player_id]
                if player_id in self.last_move_times:
                    del self.last_move_times[player_id] # Clean up time data
                del self.clients[writer]
                await self.broadcast_world_state()
            writer.close()
            await writer.wait_closed()

    async def handle_packet(self, packet, writer):
        # packet may be a parsed packet object or a raw dict
        if packet is None:
            return

        # Normalize accessors
        if hasattr(packet, "_data"):
            # parsed packet object
            data = packet.to_data()
            packet_id = getattr(packet, "packet_id", packet._data.get("_raw_id"))
        else:
            # raw dict fallback
            packet_id = packet.get("id")
            data = packet.get("data", {})

        if packet_id == PacketType.PING:
            await self.send(writer, PacketType.PONG, {"msg": "pong"})

        # Handshake/Authentication: expect PLAYER_JOIN to include 'ts' and 'hmac' proving possession of secret
        if packet_id == PacketType.PLAYER_JOIN:
            # Data may be parsed from packet object or dict
            ts = data.get("ts")
            proof = data.get("hmac")
            preferred_id = data.get("preferredId")
            nonce = self.handshake_nonces.pop(writer, None)
            if nonce is None:
                print(f"[AUTH] No handshake nonce for client, rejecting join from {writer}")
                # Disconnect
                writer.close()
                await writer.wait_closed()
                return

            # Validate timestamp
            try:
                ts = int(ts)
            except Exception:
                print(f"[AUTH] Invalid timestamp from client, rejecting")
                writer.close()
                await writer.wait_closed()
                return

            now = int(time.time())
            if abs(now - ts) > 30:
                print(f"[AUTH] Timestamp outside allowed window: {ts} (now {now})")
                writer.close()
                await writer.wait_closed()
                return

            # Validate HMAC: HMAC_SHA256(server_secret, nonce + preferredId + ts)
            msg = (nonce + (preferred_id or "") + str(ts)).encode()
            expected = hmac.new(self.server_secret.encode(), msg, hashlib.sha256).hexdigest()
            if not proof or not hmac.compare_digest(expected, proof):
                print(f"[AUTH] HMAC verification failed for client {writer}")
                writer.close()
                await writer.wait_closed()
                return

        # Handler map lookup (overrides inline logic)
        HANDLERS = {
            PacketType.PLAYER_JOIN: player_handlers.handle_player_join,
            PacketType.PLAYER_MOVE: player_handlers.handle_player_move,
            PacketType.PLAYER_CORRECTION: player_handlers.handle_player_correction,
            PacketType.CHAT: chat_handlers.handle_chat,
        }

        handler = HANDLERS.get(packet_id)
        if handler:
            await handler(self, writer, packet if hasattr(packet, "_data") else {"id": packet_id, "data": data})
            return
        else:
            print(f"[ERROR] Unknown packet type: {packet_id}")
            print(f"[ERROR] Packet data: {packet}")
            
    # Player move/correction/join logic moved to handlers/player.py
            
    async def send(self, writer, packet_id, data):
        packet = json.dumps({"id": packet_id, "data": data}) + "\n"
        writer.write(packet.encode())
        await writer.drain()

   

    async def broadcast_world_state(self):
        # Delegates to handler implementation
        await world_handlers.broadcast_world_state(self)


    async def broadcast_chat(self, msg):
        # Delegate to handler implementation
        await chat_handlers.broadcast_chat(self, msg)
    async def broadcast_npc_spawn(self, npc_id, x, y, z):
        await npc_handlers.broadcast_npc_spawn(self, npc_id, x, y, z)
        
        
    async def broadcast_npc_update(self, npc_id, x, y, z):
        await npc_handlers.broadcast_npc_update(self, npc_id, x, y, z)

    async def broadcast_npc_despawn(self, npc_id):
        await npc_handlers.broadcast_npc_despawn(self, npc_id)

    async def _broadcast(self, packet):
        # Delegate to broadcast helper (packet is string)
        from handlers.broadcast import broadcast_packet
        await broadcast_packet(self, packet)

async def main():
    server = MasterServer()
    await server.init_chat_stub()

    # Set the loop first
    server.loop = asyncio.get_running_loop()

    # Start NPCService in a background thread
    def start_npc_service():
        server.npc_service = npc_serve(server, port=7000, loop=server.loop)

    threading.Thread(target=start_npc_service, daemon=True).start()

    # TCP server setup
    tcp_server = await asyncio.start_server(server.handle_client, "127.0.0.1", 5000)
    print("[SERVER] Running MasterServer on 127.0.0.1:5000")

    # Start Chat gRPC service
    chat_server_task = asyncio.create_task(start_chat_server(6000))
    print("[CHAT] Waiting for gRPC ChatService to start...")
    await asyncio.sleep(0.1)

    # Run TCP + Chat + Chat Listener
    async with tcp_server:
        await asyncio.gather(
            tcp_server.serve_forever(),
            chat_server_task,
            server.chat.listen(["global", "trade", "guild"])
        )


if __name__ == "__main__":
    asyncio.run(main())