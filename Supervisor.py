import logging
import asyncio
from KiwoomWebsocket import KiwoomWebsocketClient
from KiwoomClient import KiwoomClient
from TradingBot import TradingBot
from typing import List


logger = logging.getLogger(__name__)


class Supervisor:
    def __init__(self, is_mock: bool, etf_list: List[str]):
        self.is_mock = is_mock
        self.etf_list = etf_list
        self.client = KiwoomClient()
        self.access_token = self.client.access_token
        self.ws_client = KiwoomWebsocketClient(is_mock=is_mock, access_token=self.access_token)
        self.trading_bot = TradingBot(client=self.client, websocket_client=self.ws_client, etf_list=self.etf_list)
    
    async def run_forever(self):
        restart_count = 0
        while True:
            try:
                logger.info("Starting trading bot run. restart_count=%s", restart_count)
                await self.trading_bot.run()
            except Exception:
                restart_count += 1
                logger.exception(
                    "Error in trading bot. restart_count=%s retry_delay_seconds=5",
                    restart_count,
                )
                logger.info("Restarting trading bot after error.")
                await asyncio.sleep(5)  # Wait for 5 seconds before restarting
