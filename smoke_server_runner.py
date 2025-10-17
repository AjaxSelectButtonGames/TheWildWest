import asyncio
import threading
from master_server import MasterServer
from chat import start_chat_server
from NPCService import serve as npc_serve

async def run_server():
    server = MasterServer()
    # Skip chat stub init which requires network grpc; start chat service in-process
    server.loop = asyncio.get_running_loop()

    # Start NPCService in a background thread if possible
    def start_npc_service():
        try:
            server.npc_service = npc_serve(server, port=7000, loop=server.loop)
        except Exception as e:
            print("[SMOKE] NPC service failed to start:", e)

    threading.Thread(target=start_npc_service, daemon=True).start()

    tcp_server = await asyncio.start_server(server.handle_client, '127.0.0.1', 5000)
    print('[SMOKE] MasterServer running on 127.0.0.1:5000')

    # Start chat server in background task
    chat_task = asyncio.create_task(start_chat_server(6000))

    async with tcp_server:
        await asyncio.gather(
            tcp_server.serve_forever(),
            chat_task,
            server.chat.listen(['global'])
        )

if __name__ == '__main__':
    asyncio.run(run_server())
