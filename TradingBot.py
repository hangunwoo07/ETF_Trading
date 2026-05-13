from KiwoomClient import KiwoomClient
from KiwoomWebsocket import KiwoomWebsocketClient
from typing import List, Dict, Optional
import logging
import asyncio


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class TradingBot:
    """A trading bot that trades ETFs based on trading strategy"""
    def __init__(self, client: KiwoomClient, websocket_client: KiwoomWebsocketClient, etf_list: List[str]):
        self.client = client
        self.ws_client = websocket_client
        self.etf_list = etf_list
        self.deposit: int = 0
        self.etf_code: str = ""
        self.did_buy: bool = False
        self.quantity: str = "0"

    async def wait_until_market_prepare_time(self):
        """
        Wait until it's time to prepare for market open (30 minutes before)
        """
        while True:
            market_time_msg: Optional[Dict] = await self.ws_client.receive_message()

            logging.info(f"Received market time message: {market_time_msg}")

            if market_time_msg is None:
                continue

            data = market_time_msg.get("data", [])

            if data and data[0].get("values").get("215") == "0":
                break
            else:
                continue
    
    async def is_market_open(self) -> bool:
        while True:
            market_time_msg: Optional[Dict] = await self.ws_client.receive_message()

            if market_time_msg is None:
                continue

            data = market_time_msg.get("data", [])
            
            if data[0].get("type") != "0s":
                continue
            
            if data[0].get("values").get("215") == "3":
                return True
    
    async def handle_realtime_message(self) -> str:
        msg = await self.ws_client.receive_message()

        if msg is None:
            return "ignore"
        
        if msg.get("trnm") != "REAL":
            logging.info(f"Received non-REAL message: {msg}")
            return "ignore"
        
        data = msg.get("data", [])
        if data and data[0].get("type") == "0B":
            percent_change: str = data[0].get("values").get("12")

            if percent_change[0] == "+":
                if float(percent_change[1:]) >= 1.0:
                    etf_price: int = int(data[0].get("values").get("10"))
                    logging.info(f"Price increased by {percent_change}, placing buy order...")

                    self.quantity = str(self.deposit // etf_price)
                    await asyncio.to_thread(self.client.buy_etf, self.etf_code, self.quantity)
                    self.did_buy = True

                    return "bought"
        
        elif data and data[0].get("type") == "0s":
            data = data[0].get("values", {})
            if data and data.get("215") == "4":
                logging.info("Market closed!")
                return "market_closed"
        
        return "ignore"

    async def run(self):
        await self.ws_client.connect()
        await self.ws_client.receive_message() # Login message

        await self.ws_client.register_market_time()
        await self.ws_client.receive_message() # REG message

        await self.wait_until_market_prepare_time()

        logging.info("Preparing for market open...")

        while True:
            # If etf_code is None, it will simply return without sending message
            # When the bot is running for the first time, etf_code will be None, so it will not send unregister message
            await self.ws_client.unregister_etf(self.etf_code)

            # Select new ETF
            self.etf_code = self.client.get_biggest_etf_volume(self.etf_list, track_range=5)
            if self.etf_code == "":
                logging.error("Failed to get ETF with biggest volume")
                continue
            logging.info(f"ETF with biggest volume: {self.etf_code}")

            self.deposit = self.client.check_deposit()
            logging.info(f"Current deposit: {self.deposit}")

            await self.ws_client.register_etf(self.etf_code)
            await self.ws_client.receive_message() # REG message

            if await self.is_market_open():
                logging.info("Market opened!")

            while True:
                result = await self.handle_realtime_message()
                if result == "bought" or result == "market_closed":
                    break
