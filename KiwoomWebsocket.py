from typing import Optional
import websockets
import json


class KiwoomWebsocketClient:
    def __init__(self, is_mock: bool, access_token: Optional[str] = None):
        if is_mock:
            self.socket_url: str = 'wss://mockapi.kiwoom.com:10000/api/dostk/websocket'
        else:
            self.socket_url: str = 'wss://api.kiwoom.com:10000/api/dostk/websocket'
        self.connected = False
        self.keep_running = True
        self.access_token = access_token
    
    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.socket_url)
            self.connected = True

            param = {
                'trnm': 'LOGIN',
                'token': self.access_token
            }

            await self.websocket.send(json.dumps(param))
        
        except Exception as e:
            print(f"Websocket connection error: {e}")
            self.connected = False
    
    async def send_message(self, message: dict):
        if not self.connected:
            raise RuntimeError("Websocket is not connected.")
        
        try:
            await self.websocket.send(json.dumps(message))
        
        except Exception as e:
            print(f"Error sending message: {e}")
    
    async def receive_message(self) -> Optional[dict]:
        if not self.connected:
            raise RuntimeError("Websocket is not connected.")
        
        try:
            response = await self.websocket.recv()
            return json.loads(response)
        
        except Exception as e:
            print(f"Error receiving message: {e}")
            return None
    
    async def register_etf(self, etf_code: str):
        # headers = {
        #     "api-id": "0B",
        #     "authorization": f"Bearer {self.access_token}",
        # }

        request = {
            "trnm": "REG",
            "grp_no": "1",
            "refresh": "0",
            "data": [
                {
                    "item": [etf_code],
                    "type": ["0B"]
                }
            ]
        }

        await self.send_message(request)


async def main():
    # Example usage
    from KiwoomClient import KiwoomClient
    client = KiwoomClient()
    access_token = client.access_token

    ws_client = KiwoomWebsocketClient(is_mock=True, access_token=access_token)
    await ws_client.connect()

    login_msg = await ws_client.receive_message()
    print(f"LOGIN message: {login_msg}")

    await ws_client.register_etf("091160")
    print("Registered ETF for real-time updates.")

    reg_msg = await ws_client.receive_message()
    print(f"REG message: {reg_msg}")

    while True:
        msg = await ws_client.receive_message()
        print(f"REALTIME message: {msg}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())