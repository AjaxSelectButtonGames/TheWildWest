import grpc
from concurrent import futures
import time
import uuid
import os
import json
import asyncio
import math
import random
import generated.npcservice_pb2 as npc_pb2
import generated.npcservice_pb2_grpc as npc_grpc


class NPCService(npc_grpc.NPCServiceServicer):
    def __init__(self, master_server, config_file="npcs.json", loop=None):
        self.master_server = master_server
        self.npcs = {}
        if loop is None:
            raise RuntimeError("Event loop must be explicitly passed to NPCService since it runs in a separate thread.")
        self.loop = loop
        self.tick = 0.25  # seconds per update
        self.load_npcs(config_file)
        # Start periodic movement loop on the master's asyncio loop
        self._movement_future = asyncio.run_coroutine_threadsafe(self._movement_loop(), self.loop)

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
                "wanderRadius": npc_def.get("wanderRadius", 0.0),
                "yaw": random.random() * 2 * math.pi,
                "speed": npc_def.get("speed", 1.5)
            }
            # Threadsafe broadcast of spawn on master's loop
            asyncio.run_coroutine_threadsafe(
                self.master_server.broadcast_npc_spawn(
                    npc_id, self.npcs[npc_id]["x"], self.npcs[npc_id]["y"], self.npcs[npc_id]["z"]
                ),
                self.loop
            )
            print(f"[NPC] Loaded NPC {npc_id} ({self.npcs[npc_id]['name']}) at {self.npcs[npc_id]['x']},{self.npcs[npc_id]['y']},{self.npcs[npc_id]['z']}")

    async def _movement_loop(self):
        while True:
            start = time.time()
            for npc_id, npc in list(self.npcs.items()):
                # wandering heading change
                npc['yaw'] = npc.get('yaw', random.random() * 2 * math.pi) + random.uniform(-0.6, 0.6) * self.tick
                speed = npc.get('speed', 1.5)
                dx = math.cos(npc['yaw']) * speed * self.tick
                dz = math.sin(npc['yaw']) * speed * self.tick
                new_x = npc['x'] + dx
                new_z = npc['z'] + dz
                new_y = self.master_server.get_height_at(new_x, new_z)

                # Bounds check
                wb = self.master_server.world_bounds
                if not (wb["min_x"] <= new_x <= wb["max_x"] and wb["min_z"] <= new_z <= wb["max_z"]):
                    npc['yaw'] += math.pi  # reverse direction
                    continue

                # Collider check
                if self.master_server.is_inside_collider(new_x, new_y, new_z):
                    npc['yaw'] += math.pi / 2
                    continue

                # Commit move
                npc.update({"x": new_x, "y": new_y, "z": new_z, "state": "walking"})
                try:
                    await self.master_server.broadcast_npc_update(npc_id, new_x, new_y, new_z)
                except Exception as e:
                    print(f"[NPC] broadcast update failed for {npc_id}: {e}")

            elapsed = time.time() - start
            await asyncio.sleep(max(0, self.tick - elapsed))

    def SpawnNPC(self, request, context):
        npc_id = str(uuid.uuid4())
        yaw = random.random() * 2 * math.pi
        speed = 1.5 + random.random() * 1.0
        self.npcs[npc_id] = {
            "x": request.x,
            "y": request.y,
            "z": request.z,
            "state": "idle",
            "yaw": yaw,
            "speed": speed,
            "name": getattr(request, "name", "npc")
        }

        # Threadsafe broadcast of spawn on master's loop
        asyncio.run_coroutine_threadsafe(
            self.master_server.broadcast_npc_spawn(npc_id, request.x, request.y, request.z),
            self.loop
        )

        print(f"[NPC] Spawned NPC {npc_id} at ({request.x}, {request.y}, {request.z})")
        return npc_pb2.NPCAck(success=True, npcId=npc_id)

     def WalkNPC(self, request, context):
        npc_id = request.npcId
        if npc_id not in self.npcs:
            return npc_pb2.NPCAck(success=False, error="NPC not found")

        self.npcs[npc_id].update({"x": request.x, "y": request.y, "z": request.z, "state": "walking"})

        asyncio.run_coroutine_threadsafe(
            self.master_server.broadcast_npc_update(npc_id, request.x, request.y, request.z),
            self.loop
        )

        print(f"[NPC] NPC {npc_id} walked to ({request.x}, {request.y}, {request.z})")
        return npc_pb2.NPCAck(success=True, npcId=npc_id)

    def DespawnNPC(self, request, context):
        npc_id = request.npcId
        if npc_id not in self.npcs:
            return npc_pb2.NPCAck(success=False, error="NPC not found")

        del self.npcs[npc_id]

        asyncio.run_coroutine_threadsafe(
            self.master_server.broadcast_npc_despawn(npc_id),
            self.loop
        )

        print(f"[NPC] Despawned NPC {npc_id}")
        return npc_pb2.NPCAck(success=True, npcId=npc_id)


# === gRPC Server Bootstrap ===
def serve(master_server, port=7000, loop=None):
    if loop is None:
        raise RuntimeError("serve() requires master event loop via loop=...")
    service = NPCService(master_server, loop=loop)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    npc_grpc.add_NPCServiceServicer_to_server(service, server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[NPC SERVICE] gRPC NPCService running on port {port}")
    return service