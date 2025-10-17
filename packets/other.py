from protocol import PacketType
from . import BasePacket
from .registry import register_packet


@register_packet
class PlayerCorrectionPacket(BasePacket):
    packet_id = PacketType.PLAYER_CORRECTION


@register_packet
class PlayerIdAssignedPacket(BasePacket):
    packet_id = PacketType.PLAYER_ID_ASSIGNED
