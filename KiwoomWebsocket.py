from typing import Optional
from config import MARKET_TIME_TYPE, ETF_REALTIME_TYPE
import logging
import websockets
import json
import asyncio


logger = logging.getLogger(__name__)


class KiwoomWebsocketClient:
    def __init__(self, is_mock: bool, access_token: Optional[str] = None):
        if is_mock:
            self.socket_url: str = 'wss://mockapi.kiwoom.com:10000/api/dostk/websocket'
        else:
            self.socket_url: str = 'wss://api.kiwoom.com:10000/api/dostk/websocket'
        self.connected = False
        self.keep_running = True
        self.access_token = access_token

        self.login_queue = asyncio.Queue()
        self.register_queue = asyncio.Queue()
        self.market_time_queue = asyncio.Queue()
        self.etf_tick_queue = asyncio.Queue()
        self.unknown_message_queue = asyncio.Queue()
    
    async def connect(self):
        try:
            logger.info("Connecting Kiwoom websocket. socket_url=%s", self.socket_url)
            self.websocket = await websockets.connect(self.socket_url)
            self.connected = True

            param = {
                'trnm': 'LOGIN',
                'token': self.access_token
            }

            await self.websocket.send(json.dumps(param))
            logger.info("Sent websocket login message.")

            self.receiver_task = asyncio.create_task(self._receive_loop())
        
        except Exception:
            self.connected = False
            logger.exception("Websocket connection error. socket_url=%s", self.socket_url)
            raise
    
    async def send_message(self, message: dict):
        if not self.connected:
            raise RuntimeError("Websocket is not connected.")
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.info(
                "Sent websocket message. trnm=%s grp_no=%s",
                message.get("trnm"),
                message.get("grp_no"),
            )
        
        except Exception:
            logger.exception("Error sending websocket message. message=%s", message)
            raise
    
    async def _receive_one_message(self) -> Optional[dict]:
        if not self.connected:
            raise RuntimeError("Websocket is not connected.")
        
        try:
            while True:
                response = await self.websocket.recv()
                message = json.loads(response)

                if message.get("trnm") == "PING":
                    await self.websocket.send(json.dumps(message))
                    # logger.info("Received websocket PING and sent heartbeat response.")
                    continue

                logger.info(
                    "Received websocket message. trnm=%s data_count=%s",
                    message.get("trnm"),
                    len(message.get("data", [])),
                )
                return message
        
        except Exception:
            self.connected = False
            logger.exception("Error receiving websocket message.")
            return None
    
    async def _receive_loop(self) -> None:
        while True:
            message = await self._receive_one_message()

            if message is None:
                continue

            if message.get("trnm") == "LOGIN":
                await self.login_queue.put(message)
            elif message.get("trnm") == "REG":
                await self.register_queue.put(message)
            elif message.get("trnm") == "REAL":
                data_entries = message.get("data") or []
                if not isinstance(data_entries, list):
                    continue

                for entry in data_entries:
                    if not isinstance(entry, dict):
                        continue

                    message_type = entry.get("type")
                    if message_type == MARKET_TIME_TYPE:
                        await self.market_time_queue.put(message)
                    elif message_type == ETF_REALTIME_TYPE:
                        await self.etf_tick_queue.put(message)
            else:
                await self.unknown_message_queue.put(message)
    
    async def wait_for_login(self, timeout: float = 10):
        """Waits for a LOGIN message from asyncio queue. Raises TimeoutError if timeout is reached."""
        return await asyncio.wait_for(self.login_queue.get(), timeout=timeout)
    
    async def wait_for_register(self, timeout: float = 10):
        """Waits for a REG message from asyncio queue. Raises TimeoutError if timeout is reached."""
        return await asyncio.wait_for(self.register_queue.get(), timeout=timeout)
    
    async def wait_for_market_time(self, timeout: float = 10):
        """Waits for a market time message from asyncio queue. Raises TimeoutError if timeout is reached."""
        return await asyncio.wait_for(self.market_time_queue.get(), timeout=timeout)

    async def wait_for_etf_tick(self, timeout: float = 10):
        """Waits for an ETF tick message from asyncio queue. Raises TimeoutError if timeout is reached."""
        return await asyncio.wait_for(self.etf_tick_queue.get(), timeout=timeout)

    async def register_etf(self, etf_code: str):
        request = {
            "trnm": "REG",
            "grp_no": "1",
            "refresh": "1",
            "data": [
                {
                    "item": [etf_code],
                    "type": [ETF_REALTIME_TYPE]
                }
            ]
        }

        await self.send_message(request)
        logger.info("Requested ETF realtime registration. etf_code=%s", etf_code)
    
    async def unregister_etf(self, etf_code: Optional[str]):
        if etf_code is None:
            return

        request = {
            "trnm": "REMOVE",
            "grp_no": "1",
            "refresh": "",
            "data": [
                {
                    "item": [etf_code],
                    "type": [ETF_REALTIME_TYPE]
                }
            ]
        }

        await self.send_message(request)
        logger.info("Requested ETF realtime unregistration. etf_code=%s", etf_code)
    
    async def register_market_time(self):
        request = {
            "trnm": "REG",
            "grp_no": "1",
            "refresh": "1",
            "data": [
                {
                    "item": [""],
                    "type": [MARKET_TIME_TYPE]
                }
            ]
        }

        await self.send_message(request)
        logger.info("Requested market-time realtime registration.")


async def main():
    # Example usage
    from KiwoomClient import KiwoomClient
    client = KiwoomClient()
    access_token = client.access_token

    ws_client = KiwoomWebsocketClient(is_mock=True, access_token=access_token)
    await ws_client.connect()

    login_msg = await ws_client.wait_for_login()
    logger.info("LOGIN message: %s", login_msg)

    await ws_client.register_etf("091160")
    logger.info("Registered ETF for real-time updates.")

    reg_msg = await ws_client.wait_for_register()
    logger.info("REG message: %s", reg_msg)

    while True:
        msg = await ws_client.wait_for_etf_tick()
        logger.info("REALTIME message: %s", msg)


if __name__ == "__main__":
    import asyncio
    from logging_config import setup_logging

    setup_logging()
    asyncio.run(main())
