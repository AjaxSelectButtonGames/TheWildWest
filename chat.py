# chat.py
import asyncio
import grpc
import configparser
import time
from generated import chatservice_pb2, chatservice_pb2_grpc


# ---------------------------
# gRPC Chat Service (server-side)
# ---------------------------
class ChatServiceServicer(chatservice_pb2_grpc.ChatServiceServicer):
    def __init__(self, channels_file="channels.ini"):
        self.channels = self.load_channels(channels_file)
        self.subscribers = {}  # channel -> set of asyncio.Queue
        print(f"[CHAT SERVER] Initialized with channels: {list(self.channels.keys())}")

    def load_channels(self, filename):
        config = configparser.ConfigParser()
        config.read(filename)
        if "channels" in config:
            return dict(config["channels"])
        else:
            return {}
    async def StreamMessages(self, request, context):
        """Client subscribes to channels, server streams back messages."""
        queue = asyncio.Queue()

        for channel in request.channels:
            self.subscribers.setdefault(channel, set()).add(queue)

        try:
            while True:
                msg = await queue.get()
                yield msg
        except asyncio.CancelledError:
            for channel in request.channels:
                self.subscribers[channel].discard(queue)
            raise

    async def SendMessage(self, request, context):
        """Broadcast message to all subscribers of a channel."""
        if request.channel not in self.channels:
            return chatservice_pb2.Ack(success=False, error="Unknown channel")

        msg = chatservice_pb2.ChatMessage(
            channel=request.channel,
            playerId=request.playerId,
            text=request.text,
            timestamp=int(time.time())
        )

        for q in self.subscribers.get(request.channel, []):
            await q.put(msg)

        return chatservice_pb2.Ack(success=True)

    async def CreateChannel(self, request, context):
        """Create a new chat channel dynamically."""
        if request.name in self.channels:
            return chatservice_pb2.Ack(success=False, error="Channel already exists")

        self.channels[request.name] = f"Created by {request.creatorId}"
        self.subscribers[request.name] = set()
        return chatservice_pb2.Ack(success=True)

    async def SendWhisper(self, request, context):
        """Send a direct message (not tied to a channel)."""
        msg = chatservice_pb2.ChatMessage(
            channel=f"whisper:{request.toPlayerId}",
            playerId=request.fromPlayerId,
            text=request.text,
            timestamp=int(time.time())
        )

        # Whispers go to a pseudo-channel just for that user
        for q in self.subscribers.get(f"whisper:{request.toPlayerId}", []):
            await q.put(msg)

        return chatservice_pb2.Ack(success=True)


async def start_chat_server(port=6000):
    """Start gRPC chat service."""
    server = grpc.aio.server()
    chatservice_pb2_grpc.add_ChatServiceServicer_to_server(ChatServiceServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    print(f"[CHAT] gRPC ChatService running on port {port}")
    await server.wait_for_termination()


# ---------------------------
# ChatManager (used by MasterServer)
# ---------------------------
class ChatManager:
    # Change __init__ to accept the stub directly
    def __init__(self, master_server, chat_stub): 
        self.master = master_server
        self.stub = chat_stub # Now self.stub is the one created by MasterServer


    async def send_message(self, player_id, text, channel="global"):
        """Send a chat message via gRPC."""
        if self.stub is None:
            print("[CHAT ERROR] ChatManager not connected yet")
            return

        msg = chatservice_pb2.ChatMessage(
            channel=channel,
            playerId=player_id,
            text=text,
            timestamp=int(time.time())
        )
        ack = await self.stub.SendMessage(msg)
        if not ack.success:
            print(f"[CHAT ERROR] {ack.error}")
        else:
            print(f"[CHAT] Sent {player_id}@{channel}: {text}")

    async def listen(self, channels):
        """Listen to gRPC chat streams and forward them to MasterServer clients."""
        if self.stub is None:
            print("[CHAT ERROR] ChatManager not connected yet")
            return

        request = chatservice_pb2.StreamRequest(playerId="server", channels=channels)
        async for msg in self.stub.StreamMessages(request):
            await self.master.broadcast_chat(msg)
