import time
import math
from protocol import PacketType


def normalize(packet_or_data):
    if hasattr(packet_or_data, "_data"):
        return packet_or_data.to_data()
    return packet_or_data.get("data", {}) if isinstance(packet_or_data, dict) else dict()


async def handle_player_join(server, writer, packet_or_data):
    data = normalize(packet_or_data)
    preferred_id = data.get("preferredId")
    assigned_id = preferred_id or str(__import__("uuid").uuid4())

    spawn_index = len(server.client_positions) % len(server.spawn_points)
    spawn_pos = server.spawn_points[spawn_index]

    server.clients[writer] = assigned_id
    server.client_positions[assigned_id] = spawn_pos
    server.last_move_times[assigned_id] = time.time()
    # Register writer and default nickname
    server.writers_by_id[assigned_id] = writer
    default_nick = data.get("nickname") or assigned_id
    server.nicknames[assigned_id] = default_nick
    server.nickname_to_id[default_nick] = assigned_id

    print(f"[JOIN] Player {assigned_id} joined at {spawn_pos}")
    await server.send(writer, PacketType.PLAYER_ID_ASSIGNED, {
        "assignedId": assigned_id,
        "spawnIndex": spawn_index
    })

    await server.broadcast_world_state()

    if hasattr(server, "npc_service"):
        for npc_id, npc in server.npc_service.npcs.items():
            print(f"[DEBUG] Sending NPC_SPAWN for {npc_id} to player {assigned_id}")
            await server.send(writer, PacketType.NPC_SPAWN, {
                "npcId": npc_id,
                "x": npc["x"],
                "y": npc["y"],
                "z": npc["z"],
                "state": npc.get("state", "idle"),
                "name": npc.get("name", "")
            })


async def handle_player_move(server, writer, packet_or_data):
    data = normalize(packet_or_data)

    player_id = server.clients.get(writer)
    if not player_id:
        print("[WARN] Move packet from unregistered client")
        return

    old_pos = server.client_positions.get(player_id, (0, 0, 0))
    old_x, old_y, old_z = old_pos

    new_x, new_y, new_z = data.get("x", 0), data.get("y", 0), data.get("z", 0)

    current_time = time.time()
    last_time = server.last_move_times.get(player_id, current_time)
    time_elapsed = current_time - last_time

    dx, dy, dz = new_x - old_x, new_y - old_y, new_z - old_z
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)

    if time_elapsed > 0.001:
        speed = dist / time_elapsed
        if speed > server.max_speed * 1.5:
            print(f"[CHEAT?] {player_id} Speed hack detected! Speed: {speed:.2f} > {server.max_speed}")
            await server.send(writer, PacketType.PLAYER_CORRECTION, {"x": old_x, "y": old_y, "z": old_z})
            return
    else:
        MAX_SINGLE_MOVE_DIST = server.max_speed * 0.2
        if dist > MAX_SINGLE_MOVE_DIST:
            print(f"[CHEAT?] {player_id} Teleport/Max dist detected! Dist: {dist:.2f} > {MAX_SINGLE_MOVE_DIST}")
            await server.send(writer, PacketType.PLAYER_CORRECTION, {"x": old_x, "y": old_y, "z": old_z})
            return

    if not (server.world_bounds["min_x"] <= new_x <= server.world_bounds["max_x"] and
            server.world_bounds["min_y"] <= new_y <= server.world_bounds["max_y"] and
            server.world_bounds["min_z"] <= new_z <= server.world_bounds["max_z"]):
        print(f"[CHEAT?] {player_id} Out of bounds at ({new_x:.2f}, {new_y:.2f}, {new_z:.2f})")
        await server.send(writer, PacketType.PLAYER_CORRECTION, {"x": old_x, "y": old_y, "z": old_z})
        return

    expected_y = server.get_height_at(new_x, new_z)
    VERTICAL_TOLERANCE = 5.0
    if abs(new_y - expected_y) > VERTICAL_TOLERANCE:
        print(f"[CHEAT?] {player_id} Invalid Y (expected {expected_y:.2f}, got {new_y:.2f}). Reverting Y only.")
        await server.send(writer, PacketType.PLAYER_CORRECTION, {"x": new_x, "y": expected_y, "z": new_z})
        return

    if server.is_inside_collider(new_x, new_y, new_z):
        print(f"[CHEAT?] {player_id} Inside collider at ({new_x:.2f}, {new_y:.2f}, {new_z:.2f})")
        await server.send(writer, PacketType.PLAYER_CORRECTION, {"x": old_x, "y": old_y, "z": old_z})
        return

    server.client_positions[player_id] = (new_x, new_y, new_z)
    server.last_move_times[player_id] = current_time
    print(f"[MOVE] Player {player_id} -> ({new_x:.2f}, {new_y:.2f}, {new_z:.2f})")
    await server.broadcast_world_state()


async def handle_player_correction(server, writer, packet_or_data):
    # If client tries to send correction, disconnect them
    player_id = server.clients.get(writer, "unknown")
    print(f"[SECURITY] {player_id} attempted to send PLAYER_CORRECTION. Disconnecting.")
    if writer in server.clients:
        del server.clients[writer]
    writer.close()
    await writer.wait_closed()
