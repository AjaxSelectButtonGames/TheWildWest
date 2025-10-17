from protocol import PacketType
from . import BasePacket
from .registry import register_packet


@register_packet
class PlayerMovePacket(BasePacket):
    packet_id = PacketType.PLAYER_MOVE
