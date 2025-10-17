from protocol import PacketType
from . import BasePacket
from .registry import register_packet


@register_packet
class PlayerJoinPacket(BasePacket):
    packet_id = PacketType.PLAYER_JOIN


@register_packet
class PlayerIdAssignedPacket(BasePacket):
    packet_id = PacketType.PLAYER_ID_ASSIGNED
