import json
from protocol import PacketType


async def broadcast_npc_spawn(server, npc_id, x, y, z):
    packet = json.dumps({
        "id": PacketType.NPC_SPAWN,
        "data": {"npcId": npc_id, "x": x, "y": y, "z": z}
    }) + "\n"
    # reuse server's _broadcast to send to all clients
    await server._broadcast(packet)
    print(f"[NPC] NPC {npc_id} spawned at: {x} {y} {z}")


async def broadcast_npc_update(server, npc_id, x, y, z):
    packet = json.dumps({
        "id": PacketType.NPC_UPDATE,
        "data": {"npcId": npc_id, "x": x, "y": y, "z": z}
    }) + "\n"
    await server._broadcast(packet)


async def broadcast_npc_despawn(server, npc_id):
    packet = json.dumps({
        "id": PacketType.NPC_DESPAWN,
        "data": {"npcId": npc_id}
    }) + "\n"
    await server._broadcast(packet)
