"""Handlers package for packet logic.
Each module exposes async handler functions with signature:
    async def handle_xxx(server, writer, packet_or_data)
"""

__all__ = ["player", "chat"]
