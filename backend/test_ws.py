import asyncio
import websockets
import json
import traceback

async def test_ws():
    try:
        async with websockets.connect('ws://localhost:8000/ws') as ws:
            print("Connected!")
            msg = await ws.recv()
            print("Received:", msg[:100])
    except Exception as e:
        print("Error:")
        traceback.print_exc()

asyncio.run(test_ws())
