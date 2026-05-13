import logging
import asyncio
from KiwoomWebsocket import KiwoomWebsocketClient
from KiwoomClient import KiwoomClient
from TradingBot import TradingBot
from typing import List


class Supervisor:
    def __init__(self, is_mock: bool, etf_list: List[str]):
        self.is_mock = is_mock
        self.etf_list = etf_list
        self.client = KiwoomClient()
        self.access_token = self.client.access_token
        self.ws_client = KiwoomWebsocketClient(is_mock=is_mock, access_token=self.access_token)
        self.trading_bot = TradingBot(client=self.client, websocket_client=self.ws_client, etf_list=self.etf_list)
    
    async def run_forever(self):
        while True:
            try:
                await self.trading_bot.run()
            except Exception as e:
                logging.error(f"Error in trading bot: {e}")
                logging.info("Restarting trading bot...")
                await asyncio.sleep(5)  # Wait for 5 seconds before restarting
