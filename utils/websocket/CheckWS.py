import asyncio
import websockets

async def test_connection():
    uri = "ws://127.0.0.1:10095"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to server")
            await websocket.send("Hello, server!")
            response = await websocket.recv()
            print(f"Received: {response}")
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.get_event_loop().run_until_complete(test_connection())