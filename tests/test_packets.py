import unittest
from packets import parse_raw_packet, BasePacket
from protocol import PacketType


class TestPackets(unittest.TestCase):
    def test_parse_known_packet(self):
        raw = {"id": PacketType.PING, "data": {"msg": "pong"}}
        pkt = parse_raw_packet(raw)
        self.assertIsNotNone(pkt)
        # Should be a BasePacket subclass (PingPacket registered)
        self.assertTrue(hasattr(pkt, "_data"))
        self.assertEqual(pkt.to_data().get("msg"), "pong")

    def test_parse_unknown_packet(self):
        raw = {"id": 99999, "data": {"foo": "bar"}}
        pkt = parse_raw_packet(raw)
        self.assertIsNotNone(pkt)
        self.assertIsInstance(pkt, BasePacket)
        self.assertEqual(pkt._data.get("foo"), "bar")
        self.assertEqual(pkt._data.get("_raw_id"), 99999)


if __name__ == "__main__":
    unittest.main()
