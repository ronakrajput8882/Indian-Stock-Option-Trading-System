import asyncio
import websockets
import json

class TickerWebSocket:
    def __init__(self, uri):
        self.uri = uri
    
    async def connect(self):
        async with websockets.connect(self.uri) as websocket:
            while True:
                data = await websocket.recv()
                print(json.loads(data))