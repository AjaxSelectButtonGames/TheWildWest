import unittest
import asyncio
from types import SimpleNamespace

from handlers.player import handle_player_join, handle_player_move
from handlers.chat import handle_chat
from protocol import PacketType


class DummyWriter:
    def __init__(self):
        self.buf = b""
        self.closed = False

    def get_extra_info(self, key):
        return ("127.0.0.1", 12345)

    def write(self, data: bytes):
        self.buf += data

    async def drain(self):
        await asyncio.sleep(0)

    def close(self):
        self.closed = True

    async def wait_closed(self):
        await asyncio.sleep(0)


class MinimalServer(SimpleNamespace):
    def __init__(self):
        super().__init__()
        self.clients = {}
        self.client_positions = {}
        self.last_move_times = {}
        self.spawn_points = [(0, 0, 0)]
        self.max_speed = 10.0
        self.world_bounds = {"min_x": -100, "max_x": 100, "min_y": -10, "max_y": 10, "min_z": -100, "max_z": 100}

    async def send(self, writer, packet_id, data):
        writer.write(str({"id": packet_id, "data": data}).encode())
        await writer.drain()

    async def broadcast_world_state(self):
        return

    def get_height_at(self, x, z):
        return 0

    def is_inside_collider(self, x, y, z):
        return False


class TestHandlers(unittest.TestCase):
    def test_player_join_and_move(self):
        server = MinimalServer()
        writer = DummyWriter()

        async def run():
            await handle_player_join(server, writer, {"data": {}})
            # writer should now be registered
            self.assertIn(writer, server.clients)
            pid = server.clients[writer]
            # Send a small move (should succeed)
            await handle_player_move(server, writer, {"data": {"x": 1, "y": 0, "z": 1}})
            self.assertIn(pid, server.client_positions)

        asyncio.run(run())

    def test_chat_handler_runs(self):
        server = MinimalServer()
        writer = DummyWriter()
        # fake chat manager
        async def send_message(player_id, text, channel):
            return

        server.chat = SimpleNamespace(send_message=send_message)
        server.clients[writer] = "player1"

        async def run():
            await handle_chat(server, writer, {"data": {"text": "hi", "channel": "global"}})

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
