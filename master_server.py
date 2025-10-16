# master_server.py
import asyncio
import json
import uuid
import grpc
import time
import math
import threading 
from protocol import PacketType
from generated import chatservice_pb2, chatservice_pb2_grpc
from chat import start_chat_server, ChatManager # ChatManager added
from NPCService import serve as npc_serve

class MasterServer:
    def __init__(self):
        self.clients = {}  # writer -> player_id
        self.client_positions = {}  # player_id -> (x, y, z)
        # New: Track last move time for velocity/speed check
        self.last_move_times = {} # player_id -> timestamp
        
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
                    packet = json.loads(message)
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
        packet_id = packet.get("id")
        data = packet.get("data", {})

        if packet_id == PacketType.PING:
            await self.send(writer, PacketType.PONG, {"msg": "pong"})

        elif packet_id == PacketType.PLAYER_JOIN:
            preferred_id = data.get("preferredId")
            assigned_id = preferred_id or str(uuid.uuid4())

            spawn_index = len(self.client_positions) % len(self.spawn_points)
            spawn_pos = self.spawn_points[spawn_index]

            self.clients[writer] = assigned_id
            self.client_positions[assigned_id] = spawn_pos
            self.last_move_times[assigned_id] = time.time() # Initialize move time
            
            print(f"[JOIN] Player {assigned_id} joined at {spawn_pos}")
            await self.send(writer, PacketType.PLAYER_ID_ASSIGNED, {
                "assignedId": assigned_id,
                "spawnIndex": spawn_index
            })

            await self.broadcast_world_state()
            
            if hasattr(self, "npc_service"):
                for npc_id, npc in self.npc_service.npcs.items():
                    print(f"[DEBUG] Sending NPC_SPAWN for {npc_id} to player {assigned_id}")
                    await self.send(writer, PacketType.NPC_SPAWN, {
                        "npcId": npc_id,
                        "x": npc["x"],
                        "y": npc["y"],
                        "z": npc["z"],
                        "state": npc.get("state", "idle"),
                        "name": npc.get("name", "")
                    })
                    
            
        elif packet_id == PacketType.PLAYER_MOVE:
            await self.handle_player_move(writer, data)
            
        elif packet_id == PacketType.CHAT:
            player_id = self.clients.get(writer, "unknown")
            msg_text = data.get("text", "")
            channel = data.get("channel", "global")

            await self.chat.send_message(player_id, msg_text, channel)
        elif packet_id == PacketType.PLAYER_CORRECTION:
            player_id = self.clients.get(writer, "unknown")
            print(f"[SECURITY] {player_id} attempted to send PLAYER_CORRECTION. Disconnecting.")
            # Disconnect this client
            if writer in self.clients:
                del self.clients[writer]
            writer.close()
            await writer.wait_closed()
            return
        else:
            print(f"[ERROR] Unknown packet type: {packet_id}")
            print(f"[ERROR] Packet data: {packet}")
            
    async def handle_player_move(self, writer, data):
        # BUG FIX 1: Corrected self.cleints to self.clients
        player_id = self.clients.get(writer)
        if not player_id:
            print("[WARN] Move packet from unregistered client")
            return
            
        # Get old position, default to current if missing (shouldn't happen post-join)
        old_pos = self.client_positions.get(player_id, (0, 0, 0))
        old_x, old_y, old_z = old_pos
            
        new_x, new_y, new_z = data.get("x", 0), data.get("y", 0), data.get("z", 0)
        
        # --- 1. Speed/Velocity Check ---
        # NOTE: Your initial check was a simplified "max distance per packet."
        # The correct velocity check uses time.
        
        current_time = time.time()
        last_time = self.last_move_times.get(player_id, current_time)
        time_elapsed = current_time - last_time
        
        dx, dy, dz = new_x - old_x, new_y - old_y, new_z - old_z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        
        # Guard against zero division and tiny time steps
        if time_elapsed > 0.001: 
            speed = dist / time_elapsed
            
            if speed > self.max_speed * 1.5: # 1.5x buffer for latency/jitter
                print(f"[CHEAT?] {player_id} Speed hack detected! Speed: {speed:.2f} > {self.max_speed}")
                await self.send(writer, PacketType.PLAYER_CORRECTION, {
                    "x": old_x, "y": old_y, "z": old_z
                })
                return
        else:
            # If no time elapsed, check for instantaneous teleport (large distance jump)
            # Max distance in a single packet (e.g., if server tick is 0.1s, max_dist is 1.0)
            MAX_SINGLE_MOVE_DIST = self.max_speed * 0.2 
            if dist > MAX_SINGLE_MOVE_DIST:
                 print(f"[CHEAT?] {player_id} Teleport/Max dist detected! Dist: {dist:.2f} > {MAX_SINGLE_MOVE_DIST}")
                 await self.send(writer, PacketType.PLAYER_CORRECTION, {
                    "x": old_x, "y": old_y, "z": old_z
                 })
                 return

        # --- 2. World Bounds Check ---
        # BUG FIX 2: Your old code checked 'new_x' for y and z bounds. Corrected.
        if not (self.world_bounds["min_x"] <= new_x <= self.world_bounds["max_x"] and
                self.world_bounds["min_y"] <= new_y <= self.world_bounds["max_y"] and # Corrected from new_x to new_y
                self.world_bounds["min_z"] <= new_z <= self.world_bounds["max_z"]): # Corrected from new_x to new_z
            print(f"[CHEAT?] {player_id} Out of bounds at ({new_x:.2f}, {new_y:.2f}, {new_z:.2f})")
            await self.send(writer, PacketType.PLAYER_CORRECTION, {
                "x": old_x, "y": old_y, "z": old_z
            })
            return
            
        # --- 3. Ground/Heightmap Check (Vertical only) ---
        # This checks if the player is at the expected ground level or hovering/falling too far
        expected_y = self.get_height_at(new_x, new_z)
        # Allow a reasonable tolerance for client-side physics jitter and jumps (e.g., player_height + jump_height)
        VERTICAL_TOLERANCE = 5.0 
        
        if abs(new_y - expected_y) > VERTICAL_TOLERANCE:
            print(f"[CHEAT?] {player_id} Invalid Y (expected {expected_y:.2f}, got {new_y:.2f}). Reverting Y only.")
            
            # Send correction packet with corrected Y, but using new X/Z for smooth horizontal movement
            await self.send(writer, PacketType.PLAYER_CORRECTION, {
                "x": new_x, "y": expected_y, "z": new_z
            })
            
            # We reject the vertical change but can accept the horizontal if desired, 
            # or revert the whole thing to be safe. Reverting all to old_pos is safest.
            # For max safety:
            # return
            
            # Since we send a correction, we revert the server's state to old_pos and return
            return
            
        # --- 4. Collider/Wall Check ---
        # Checks if the player is inside an object
        if self.is_inside_collider(new_x, new_y, new_z):
            print(f"[CHEAT?] {player_id} Inside collider at ({new_x:.2f}, {new_y:.2f}, {new_z:.2f})")
            await self.send(writer, PacketType.PLAYER_CORRECTION, {
                "x": old_x, "y": old_y, "z": old_z
            })
            return
            
        # --- ACCEPT MOVE ---
        self.client_positions[player_id] = (new_x, new_y, new_z)
        self.last_move_times[player_id] = current_time # Update time
        print(f"[MOVE] Player {player_id} -> ({new_x:.2f}, {new_y:.2f}, {new_z:.2f})")
        await self.broadcast_world_state()
            
    async def send(self, writer, packet_id, data):
        packet = json.dumps({"id": packet_id, "data": data}) + "\n"
        writer.write(packet.encode())
        await writer.drain()

   

    async def broadcast_world_state(self):
        players = [
            {"id": pid, "x": pos[0], "y": pos[1], "z": pos[2]}
            for pid, pos in self.client_positions.items()
        ]
        packet = json.dumps({
            "id": PacketType.WORLD_UPDATE,
            "data": {"players": players}
        }) + "\n"

        print(f"[BROADCAST] {len(players)} players")

        dead_clients = []
        for w in list(self.clients.keys()):
            try:
                w.write(packet.encode())
                await w.drain()
            except Exception as e:
                print(f"[ERROR] Broadcast to client failed: {e}")
                dead_clients.append(w)

        for w in dead_clients:
            player_id = self.clients.pop(w, None)
            if player_id and player_id in self.client_positions:
                del self.client_positions[player_id]
                print(f"[CLEANUP] Removed dead client {player_id}")


    async def broadcast_chat(self, msg):
        """Send a chat message from gRPC service to all connected clients."""
        packet = json.dumps({
            "id": PacketType.CHAT,
            "data": {
                "channel": msg.channel,
                "playerId": msg.playerId,
                "text": msg.text,
                "timestamp": msg.timestamp
            }
        }) + "\n"
        json_str = json.dumps(packet) + "\n"
        print(f"[BROADCAST CHAT] Sending: {json_str}") 
        for w in list(self.clients.keys()):
            try:
                w.write(packet.encode())
                await w.drain()
            except Exception:
                pass
    async def broadcast_npc_spawn(self, npc_id, x, y, z):
        packet = json.dumps({
            "id": PacketType.NPC_SPAWN,
            "data": {"npcId": npc_id, "x": x, "y": y, "z": z}
        }) + "\n"
        await self._broadcast(packet)
        print(f"[NPC] NPC {npcId} spawned at: {x} {y} {z}")
        
        
    async def broadcast_npc_update(self, npc_id, x, y, z):
        packet = json.dumps({
            "id": PacketType.NPC_UPDATE,
            "data": {"npcId": npc_id, "x": x, "y": y, "z": z}
        }) + "\n"
        await self._broadcast(packet)

    async def broadcast_npc_despawn(self, npc_id):
        packet = json.dumps({
            "id": PacketType.NPC_DESPAWN,
            "data": {"npcId": npc_id}
        }) + "\n"
        await self._broadcast(packet)

    async def _broadcast(self, packet):
        dead_clients = []
        for w in list(self.clients.keys()):
            try:
                w.write(packet.encode())
                await w.drain()
            except Exception as e:
                print(f"[ERROR] Failed to broadcast to client: {e}")
                dead_clients.append(w)

        for w in dead_clients:
            player_id = self.clients.pop(w, None)
            if player_id and player_id in self.client_positions:
                del self.client_positions[player_id]
                print(f"[CLEANUP] Removed dead client {player_id}")

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