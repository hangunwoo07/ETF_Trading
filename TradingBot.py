from KiwoomClient import KiwoomClient
from KiwoomWebsocket import KiwoomWebsocketClient
from typing import List, Dict, Optional
import logging
import asyncio


logger = logging.getLogger(__name__)


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

            if market_time_msg is None:
                logger.info("Ignoring empty market-time message.")
                continue

            data = market_time_msg.get("data", [])
            market_status = data[0].get("values", {}).get("215") if data else None
            logger.info(
                "Received market-time message. market_status=%s raw_message=%s",
                market_status,
                market_time_msg,
            )

            if market_status == "0":
                break
            else:
                continue
    
    async def is_market_open(self) -> bool:
        while True:
            market_time_msg: Optional[Dict] = await self.ws_client.receive_message()

            if market_time_msg is None:
                logger.info("Ignoring empty market-open message.")
                continue

            data = market_time_msg.get("data", [])

            if not data:
                logger.info("Ignoring market-open message without data. message=%s", market_time_msg)
                continue

            message_type = data[0].get("type")
            if message_type != "0s":
                logger.info(
                    "Ignoring non-market-time message while waiting for market open. message_type=%s",
                    message_type,
                )
                continue
            
            market_status = data[0].get("values", {}).get("215")
            logger.info("Market status while waiting for open. market_status=%s", market_status)

            if market_status == "3":
                return True
    
    async def handle_realtime_message(self) -> str:
        msg = await self.ws_client.receive_message()

        if msg is None:
            logger.info("Ignoring empty realtime message.")
            return "ignore"
        
        if msg.get("trnm") != "REAL":
            logger.info("Received non-REAL realtime message. trnm=%s message=%s", msg.get("trnm"), msg)
            return "ignore"
        
        data = msg.get("data", [])
        if data and data[0].get("type") == "0B":
            values = data[0].get("values", {})
            percent_change: str = values.get("12")
            current_price = values.get("10")
            logger.info(
                "Received ETF realtime price message. etf_code=%s percent_change=%s current_price=%s did_buy=%s",
                self.etf_code,
                percent_change,
                current_price,
                self.did_buy,
            )

            if percent_change and percent_change[0] == "+":
                if float(percent_change[1:]) >= 1.0:
                    etf_price: int = int(current_price)

                    self.quantity = str(self.deposit // etf_price)
                    logger.info(
                        "Price threshold reached. placing buy order. etf_code=%s percent_change=%s price=%s deposit=%s quantity=%s",
                        self.etf_code,
                        percent_change,
                        etf_price,
                        self.deposit,
                        self.quantity,
                    )
                    await asyncio.to_thread(self.client.buy_etf, self.etf_code, self.quantity)
                    self.did_buy = True

                    return "bought"
        
        elif data and data[0].get("type") == "0s":
            data = data[0].get("values", {})
            if data and data.get("215") == "4":
                logger.info("Market closed. market_status=%s", data.get("215"))
                return "market_closed"
        
        return "ignore"

    async def run(self):
        logger.info("Connecting websocket for trading bot.")
        await self.ws_client.connect()
        login_msg = await self.ws_client.receive_message()
        logger.info("Received websocket login response. message=%s", login_msg)

        await self.ws_client.register_market_time()
        market_time_reg_msg = await self.ws_client.receive_message()
        logger.info("Registered market-time feed. response=%s", market_time_reg_msg)

        logger.info("Waiting until market prepare time.")

        await self.wait_until_market_prepare_time()

        logger.info("Preparing for market open.")

        while True:
            # If etf_code is None, it will simply return without sending message
            # When the bot is running for the first time, etf_code will be None, so it will not send unregister message
            await self.ws_client.unregister_etf(self.etf_code)

            # Select new ETF
            self.etf_code = self.client.get_biggest_etf_volume(self.etf_list, track_range=5)
            if self.etf_code == "":
                logger.error("Failed to get ETF with biggest volume. etf_count=%s", len(self.etf_list))
                continue
            logger.info("Selected ETF with biggest volume. etf_code=%s", self.etf_code)

            self.deposit = self.client.check_deposit()
            logger.info("Checked current deposit. deposit=%s", self.deposit)

            await self.ws_client.register_etf(self.etf_code)
            etf_reg_msg = await self.ws_client.receive_message()
            logger.info("Registered ETF realtime feed. etf_code=%s response=%s", self.etf_code, etf_reg_msg)

            if await self.is_market_open():
                logger.info("Market opened.")

            while True:
                result = await self.handle_realtime_message()
                if result == "bought" or result == "market_closed":
                    logger.info("Finished realtime handling cycle. result=%s etf_code=%s", result, self.etf_code)
                    break
