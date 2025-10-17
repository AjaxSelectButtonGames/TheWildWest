from protocol import PacketType
from . import BasePacket
from .registry import register_packet


@register_packet
class ChatPacket(BasePacket):
    packet_id = PacketType.CHAT
