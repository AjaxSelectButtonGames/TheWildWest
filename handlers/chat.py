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
