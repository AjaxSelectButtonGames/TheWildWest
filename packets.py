from typing import Type, Dict, Any, Optional
from protocol import PacketType


class BasePacket:
    packet_id: int = None

    def __init__(self, **kwargs):
        # store raw data so we remain flexible with fields
        self._data = dict(kwargs)

    @classmethod
    def from_data(cls, data: Dict[str, Any]):
        # Build a packet instance from raw data(dict)
        return cls(**data)

    def to_data(self) -> Dict[str, Any]:
        # convert packet into serializable dict
        return dict(self._data)

    def __getattr__(self, item):
        # fallback to data keys for convenience
        if item in self._data:
            return self._data[item]
        raise AttributeError(item)


# Registry to map packet ids to classes
_registry: Dict[int, Type[BasePacket]] = {}


def register_packet(cls: Type[BasePacket]):
    pid = getattr(cls, "packet_id", None)
    if pid is None:
        raise ValueError("packet class must define packet_id")
    _registry[pid] = cls
    return cls


def parse_raw_packet(raw: Dict[str, Any]) -> Optional[BasePacket]:
    """Parse a raw dict (with keys 'id' and 'data') into a packet object.

    Returns None if the packet id is unknown.
    """
    if not raw:
        return None
    pid = raw.get("id")
    data = raw.get("data", {}) or {}
    cls = _registry.get(pid)
    if cls:
        return cls.from_data(data)
    # Fallback: return a generic BasePacket with the provided id included
    p = BasePacket(**data)
    p._data["_raw_id"] = pid
    return p


# Concrete packets commonly used by server. Keep minimal so we don't change behavior.
@register_packet
class PingPacket(BasePacket):
    packet_id = PacketType.PING


@register_packet
class PongPacket(BasePacket):
    packet_id = PacketType.PONG


@register_packet
class PlayerJoinPacket(BasePacket):
    packet_id = PacketType.PLAYER_JOIN


@register_packet
class PlayerIdAssignedPacket(BasePacket):
    packet_id = PacketType.PLAYER_ID_ASSIGNED


@register_packet
class PlayerMovePacket(BasePacket):
    packet_id = PacketType.PLAYER_MOVE


@register_packet
class ChatPacket(BasePacket):
    packet_id = PacketType.CHAT


@register_packet
class PlayerCorrectionPacket(BasePacket):
    packet_id = PacketType.PLAYER_CORRECTION


@register_packet
class WorldUpdatePacket(BasePacket):
    packet_id = PacketType.WORLD_UPDATE


@register_packet
class NpcSpawnPacket(BasePacket):
    packet_id = PacketType.NPC_SPAWN


@register_packet
class NpcUpdatePacket(BasePacket):
    packet_id = PacketType.NPC_UPDATE


@register_packet
class NpcDespawnPacket(BasePacket):
    packet_id = PacketType.NPC_DESPAWN
