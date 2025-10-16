import grpc
from concurrent import futures
import time
import uuid
import os 
import json
import asyncio # <-- ADDED: Needed for run_coroutine_threadsafe
# Make sure these match the actual generated filenames inside /generated
import generated.npcservice_pb2 as npc_pb2
import generated.npcservice_pb2_grpc as npc_grpc


class NPCService(npc_grpc.NPCServiceServicer):
    # CRITICAL FIX: Accept the loop passed from the main thread
    def __init__(self, master_server, config_file="npcs.json", loop=None): 
        self.master_server = master_server
        self.npcs = {}
        
        # CRITICAL FIX: Ensure the loop is passed; we cannot call asyncio.get_event_loop() 
        # when running in a new synchronous thread.
        if loop is None:
            # Raise an error if the calling code (master_server.py) did not pass the loop
            raise RuntimeError("Event loop must be explicitly passed to NPCService since it runs in a separate thread.")
            
        self.loop = loop
        self.load_npcs(config_file)
        
    def load_npcs(self, config_file):
        if not os.path.exists(config_file):
            print(f"[NPC] Config file {config_file} not found, skipping preload.")
            return

        with open(config_file, "r") as f:
            data = json.load(f)

        for npc_def in data.get("npcs", []):
            npc_id = npc_def["id"]
            self.npcs[npc_id] = {
                "name": npc_def.get("name", "Unknown"),
                "type": npc_def.get("type", "generic"),
                "x": npc_def["spawn"]["x"],
                "y": npc_def["spawn"]["y"],
                "z": npc_def["spawn"]["z"],
                "state": npc_def.get("behavior", "idle"),
                "wanderRadius": npc_def.get("wanderRadius", 0.0)
            }
            # FIX: Use run_coroutine_threadsafe to safely execute the async broadcast
            # on the main MasterServer event loop, preventing the RuntimeWarning.
            asyncio.run_coroutine_threadsafe(
                self.master_server.broadcast_npc_spawn(
                    npc_id, self.npcs[npc_id]["x"], self.npcs[npc_id]["y"], self.npcs[npc_id]["z"]
                ),
                self.loop # Use the stored loop
            )
            print(f"[NPC] Loaded NPC {npc_id} ({self.npcs[npc_id]['name']}) at {self.npcs[npc_id]['x']},{self.npcs[npc_id]['y']},{self.npcs[npc_id]['z']}")
            
    def SpawnNPC(self, request, context):
        npc_id = str(uuid.uuid4())
        self.npcs[npc_id] = {
            "x": request.x,
            "y": request.y,
            "z": request.z,
            "state": "idle"
        }

        # Threadsafe call to asyncio loop
        asyncio.run_coroutine_threadsafe(
            self.master_server.broadcast_npc_spawn(npc_id, request.x, request.y, request.z),
            self.loop # Use the stored loop
        )

        print(f"[NPC] Spawned NPC {npc_id} at ({request.x}, {request.y}, {request.z})")
        return npc_pb2.NPCAck(success=True, npcId=npc_id)

    def WalkNPC(self, request, context):
        npc_id = request.npcId
        if npc_id not in self.npcs:
            return npc_pb2.NPCAck(success=False, error="NPC not found")

        self.npcs[npc_id].update({"x": request.x, "y": request.y, "z": request.z, "state": "walking"})

        # Threadsafe call
        asyncio.run_coroutine_threadsafe(
            self.master_server.broadcast_npc_update(npc_id, request.x, request.y, request.z),
            self.loop # Use the stored loop
        )

        print(f"[NPC] NPC {npc_id} walked to ({request.x}, {request.y}, {request.z})")
        return npc_pb2.NPCAck(success=True, npcId=npc_id)

    def DespawnNPC(self, request, context):
        npc_id = request.npcId
        if npc_id not in self.npcs:
            return npc_pb2.NPCAck(success=False, error="NPC not found")

        del self.npcs[npc_id]

        # Threadsafe call
        asyncio.run_coroutine_threadsafe(
            self.master_server.broadcast_npc_despawn(npc_id),
            self.loop # Use the stored loop
        )

        print(f"[NPC] Despawned NPC {npc_id}")
        return npc_pb2.NPCAck(success=True, npcId=npc_id)


# === gRPC Server Bootstrap ===
# CRITICAL FIX: Accept the main loop as an argument
def serve(master_server, port=7000, loop=None):
    service = NPCService(master_server, loop=loop)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    npc_grpc.add_NPCServiceServicer_to_server(service, server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[NPC SERVICE] gRPC NPCService running on port {port}")
    return service
