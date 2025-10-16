import asyncio
import grpc
import time
from concurrent import futures
from generated import chatservice_pb2, chatservice_pb2_grpc


class ChatService(chat_pb2_grpc.ChatServiceServicer):
    def __init__(self):
        # channel_name -> set of (playerId, queue)
        self.channels = {}
        # Preload channels from config
        for name in ["global", "trade", "guild"]:
            self.channels[name] = {}

    async def _broadcast(self, channel, message):
        """Send a message to all subscribers of a channel."""
        if channel not in self.channels:
            return
        for queue in self.channels[channel].values():
            await queue.put(message)

    async def _deliver_whisper(self, toPlayerId, message):
        """Deliver whisper to a specific player (search across channels)."""
        found = False
        for chan, subs in self.channels.items():
            if toPlayerId in subs:
                await subs[toPlayerId].put(message)
                found = True
        return found

    async def StreamMessages(self, request, context):
        """Client subscribes to channels and gets a stream of messages."""
        queues = []
        player_id = request.playerId

        for channel in request.channels:
            if channel not in self.channels:
                self.channels[channel] = {}
            queue = asyncio.Queue()
            self.channels[channel][player_id] = queue
            queues.append(queue)

        try:
            while True:
                # Wait for any message from any subscribed channel
                done, _ = await asyncio.wait(
                    [asyncio.create_task(q.get()) for q in queues],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    msg = task.result()
                    yield msg
        finally:
            # Clean up on disconnect
            for channel in request.channels:
                if player_id in self.channels[channel]:
                    del self.channels[channel][player_id]

    async def SendMessage(self, request, context):
        """Broadcast a chat message to a channel."""
        msg = chat_pb2.ChatMessage(
            channel=request.channel,
            playerId=request.playerId,
            text=request.text,
            timestamp=int(time.time())
        )
        await self._broadcast(request.channel, msg)
        return chat_pb2.Ack(success=True)

    async def SendWhisper(self, request, context):
        """Send a private message (whisper)."""
        msg = chat_pb2.ChatMessage(
            channel="whisper",
            playerId=request.fromPlayerId,
            text=f"(whisper to {request.toPlayerId}): {request.text}",
            timestamp=int(time.time())
        )
        success = await self._deliver_whisper(request.toPlayerId, msg)
        if not success:
            return chat_pb2.Ack(success=False, error="Target not online")
        return chat_pb2.Ack(success=True)

    async def CreateChannel(self, request, context):
        """Create a new channel."""
        if request.name in self.channels:
            return chat_pb2.Ack(success=False, error="Channel already exists")
        self.channels[request.name] = {}
        return chat_pb2.Ack(success=True)


async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(), server)
    server.add_insecure_port("[::]:6000")
    print("[CHAT SERVER] Running on port 6000")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
