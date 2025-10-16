import json
from protocol import PacketType

class PacketFactory:
    @staticmethod
    def build(packet_id: int, data: dict) -> str:
        """Serialize a packet to a JSON string."""
        packet = {"id": packet_id, "data": data}
        return json.dumps(packet)

    @staticmethod
    def parse(raw_data: str):
        """Deserialize raw packet data into a dict."""
        try:
            packet = json.loads(raw_data)
            return packet.get("id"), packet.get("data")
        except json.JSONDecodeError:
            return None, None
