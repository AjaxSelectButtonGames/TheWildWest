from protocol import PacketType
from . import BasePacket
from .registry import register_packet


@register_packet
class NpcSpawnPacket(BasePacket):
    packet_id = PacketType.NPC_SPAWN


@register_packet
class NpcUpdatePacket(BasePacket):
    packet_id = PacketType.NPC_UPDATE


@register_packet
class NpcDespawnPacket(BasePacket):
    packet_id = PacketType.NPC_DESPAWN
