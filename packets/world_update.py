from protocol import PacketType
from . import BasePacket
from .registry import register_packet


@register_packet
class WorldUpdatePacket(BasePacket):
    packet_id = PacketType.WORLD_UPDATE
