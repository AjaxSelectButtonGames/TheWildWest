from protocol import PacketType
from .broadcast import broadcast_packet
import json


def normalize(packet_or_data):
    if hasattr(packet_or_data, "_data"):
        return packet_or_data.to_data()
    return packet_or_data.get("data", {}) if isinstance(packet_or_data, dict) else dict()


async def handle_chat(server, writer, packet_or_data):
    data = normalize(packet_or_data)
    player_id = server.clients.get(writer, "unknown")
    msg_text = data.get("text", "")
    channel = data.get("channel", "global")

    # Simple chat commands: /nick <name> and /whisper <playername> <message>
    if msg_text.startswith("/nick "):
        parts = msg_text.split(None, 1)
        if len(parts) < 2:
            return
        new_nick = parts[1].strip()
        # Check if nickname already in use
        if new_nick in server.nickname_to_id:
            # send a private correction/notice back to the user
            await server.send(writer, PacketType.CHAT, {"text": f"Nickname {new_nick} is already in use.", "channel": "system"})
            return
        old = server.nicknames.get(player_id)
        if old:
            del server.nickname_to_id[old]
        server.nicknames[player_id] = new_nick
        server.nickname_to_id[new_nick] = player_id
        await server.send(writer, PacketType.CHAT, {"text": f"Nickname changed to {new_nick}", "channel": "system"})
        return

    if msg_text.startswith("/whisper "):
        parts = msg_text.split(None, 2)
        if len(parts) < 3:
            await server.send(writer, PacketType.CHAT, {"text": "Usage: /whisper <playername> <message>", "channel": "system"})
            return
        target, message = parts[1], parts[2]
        target_id = server.nickname_to_id.get(target)
        if not target_id:
            await server.send(writer, PacketType.CHAT, {"text": f"Player {target} not found.", "channel": "system"})
            return
        target_writer = server.writers_by_id.get(target_id)
        if not target_writer:
            await server.send(writer, PacketType.CHAT, {"text": f"Player {target} is offline.", "channel": "system"})
            return
        # send private message to target and a confirmation to sender
        await server.send(target_writer, PacketType.CHAT, {"text": message, "channel": f"whisper:{server.nicknames.get(player_id,player_id)}", "playerId": player_id})
        await server.send(writer, PacketType.CHAT, {"text": f"(whisper to {target}) {message}", "channel": "system"})
        return

    await server.chat.send_message(player_id, msg_text, channel)


async def broadcast_chat(server, msg):
    packet = json.dumps({
        "id": PacketType.CHAT,
        "data": {
            "channel": msg.channel,
            "playerId": msg.playerId,
            "text": msg.text,
            "timestamp": msg.timestamp
        }
    }) + "\n"
    print(f"[BROADCAST CHAT] Sending: {packet}")
    await broadcast_packet(server, packet)
