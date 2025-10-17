from typing import Type, Dict, Any


class _Reg:
    pass


_registry: Dict[int, Type] = {}


def register_packet(cls: Type):
    pid = getattr(cls, "packet_id", None)
    if pid is None:
        raise ValueError("packet class must define packet_id")
    _registry[pid] = cls
    return cls
