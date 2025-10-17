from typing import Type, Dict, Any, Optional
from .registry import register_packet, _registry


class BasePacket:
    packet_id: int = None

    def __init__(self, **kwargs):
        self._data = dict(kwargs)

    @classmethod
    def from_data(cls, data: Dict[str, Any]):
        return cls(**data)

    def to_data(self) -> Dict[str, Any]:
        return dict(self._data)

    def __getattr__(self, item):
        if item in self._data:
            return self._data[item]
        raise AttributeError(item)


def parse_raw_packet(raw: Dict[str, Any]) -> Optional[BasePacket]:
    if not raw:
        return None
    pid = raw.get("id")
    data = raw.get("data", {}) or {}
    cls = _registry.get(pid)
    if cls:
        return cls.from_data(data)
    p = BasePacket(**data)
    p._data["_raw_id"] = pid
    return p

# Expose registry utilities for modules
__all__ = [
    "BasePacket",
    "parse_raw_packet",
    "register_packet",
]

# Import concrete packet modules so they register themselves on package import
# This keeps registration centralized: adding a new packet module should be
# added here so it's picked up automatically.
from . import ping  # noqa: F401
from . import player_join  # noqa: F401
from . import player_move  # noqa: F401
from . import chat as chat_packets  # noqa: F401
from . import npc as npc_packets  # noqa: F401
from . import world_update as world_packets  # noqa: F401
from . import other as other_packets  # noqa: F401
