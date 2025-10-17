from protocol import PacketType
from . import BasePacket
from .registry import register_packet


@register_packet
class PingPacket(BasePacket):
    packet_id = PacketType.PING


@register_packet
class PongPacket(BasePacket):
    packet_id = PacketType.PONG
