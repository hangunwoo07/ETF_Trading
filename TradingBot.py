from KiwoomClient import KiwoomClient
from KiwoomWebsocket import KiwoomWebsocketClient
from config import MARKET_STATE_KEY, MARKET_OPEN_KEY, MARKET_PRE_OPEN_KEY, MARKET_CLOSED_KEY
from zoneinfo import ZoneInfo
from enum import Enum
from dataclasses import dataclass
import exchange_calendars as xcals
import datetime
import logging
import asyncio


logger = logging.getLogger(__name__)


class MarketState(Enum):
    UNKNOWN = "unknown"
    PRE_OPEN = "pre_open"
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class TradingState:
    deposit: int = 0
    etf_code: str = ""
    did_buy: bool = False
    quantity: str = "0"
    market_state: MarketState = MarketState.UNKNOWN


def get_csat_date(year: int) -> datetime.date:
    d = datetime.date(year, 11, 13)
    days_until_thursday = (3 - d.weekday()) % 7
    return d + datetime.timedelta(days=days_until_thursday)


def is_today_csat_day() -> bool:
    today = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()
    return today == get_csat_date(today.year)


def _is_market_open_based_datetime() -> MarketState:
    """Check if the market is open based on exchange calendar and current time"""
    calendar = xcals.get_calendar("XKRX")
    today = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date()

    if not calendar.is_session(today):
        return MarketState.CLOSED
    
    if is_today_csat_day():
        market_open_time = datetime.time(10, 0)
    else:
        market_open_time = datetime.time(9, 0)
    market_close_time = datetime.time(15, 30)
    now_time = datetime.datetime.now(ZoneInfo("Asia/Seoul")).time()

    return MarketState.OPEN if market_open_time <= now_time <= market_close_time else MarketState.CLOSED


class TradingBot:
    """A trading bot that trades ETFs based on trading strategy"""
    def __init__(self, client: KiwoomClient, websocket_client: KiwoomWebsocketClient, etf_list: list[str]):
        self.client = client
        self.ws_client = websocket_client
        self.etf_list = etf_list
        self.quantity: str = "0"
    
    def _parse_market_state(self, market_time_msg: dict | None) -> MarketState:
        if market_time_msg is None:
            return MarketState.UNKNOWN

        data = market_time_msg.get("data", [])

        if not data:
            logger.info(
                "Market-time message without data. message=%s",
                market_time_msg,
            )
            return MarketState.UNKNOWN

        market_status = data[0].get("values", {}).get(MARKET_STATE_KEY)

        if market_status in MARKET_PRE_OPEN_KEY:
            return MarketState.PRE_OPEN
        elif market_status in MARKET_OPEN_KEY:
            return MarketState.OPEN
        elif market_status in MARKET_CLOSED_KEY:
            return MarketState.CLOSED
        else:
            return MarketState.UNKNOWN

    async def _monitor_market_state(
        self,
        trading_state: TradingState,
        stop_event: asyncio.Event,
        market_state_ready: asyncio.Event,
    ) -> None:
        """
        Continuously monitors market-time messages and updates trading_state.market_state.
        """
        try:
            market_state = await self._get_market_state_with_fallback()
            trading_state.market_state = market_state
            market_state_ready.set() # Set market_state_ready event after getting initial market state

            if market_state == MarketState.CLOSED:
                stop_event.set()
                return
            
            while not stop_event.is_set():
                try:
                    market_time_msg = await self.ws_client.wait_for_market_time()
                    market_state = self._parse_market_state(market_time_msg)

                    if market_state == MarketState.UNKNOWN:
                        logger.info("Market state is unknown from websocket. Using datetime fallback.")
                        market_state = _is_market_open_based_datetime()

                except asyncio.TimeoutError:
                    logger.info("Timeout while waiting for market-time message. Using datetime fallback.")
                    market_state = _is_market_open_based_datetime()

                trading_state.market_state = market_state
                market_state_ready.set()

                logger.info("Updated market_state=%s", trading_state.market_state)

                if trading_state.market_state == MarketState.CLOSED:
                    stop_event.set()

        except asyncio.CancelledError:
            logger.info("Market-state monitor cancelled during initial market state retrieval.")
            raise
    
    async def _get_market_state_with_fallback(self, timeout: float = 10) -> MarketState:
        """Used to get initial market state when starting the bot."""
        try:
            market_time_msg = await self.ws_client.wait_for_market_time(timeout=timeout)
            market_state = self._parse_market_state(market_time_msg)

            if market_state != MarketState.UNKNOWN:
                return market_state

            logger.info(
                "Market state is UNKNOWN from websocket. Checking market state based on datetime."
            )
            return _is_market_open_based_datetime()

        except asyncio.TimeoutError:
            logger.info(
                "Timeout while waiting for market-time message. Checking market state based on datetime."
            )
            return _is_market_open_based_datetime()

    async def _handle_etf_message_and_buy(self, trading_state: TradingState, stop_event: asyncio.Event) -> TradingState:
        """Handle ETF tick message and decide whether to buy or not. Return updated trading state."""
        try:
            etf_msg = await self.ws_client.wait_for_etf_tick()
        except asyncio.TimeoutError:
            logger.info("Timeout while waiting for ETF tick message. Returning current trading state. etf_code=%s", trading_state.etf_code)
            return trading_state

        if etf_msg is None:
            logger.info("Empty ETF tick message.")
            return trading_state
        
        values = etf_msg.get("data", [])[0].get("values", {})
        percent_change: str = values.get("12")
        current_price = values.get("10")

        if percent_change and percent_change[0] == "+":
            if float(percent_change[1:]) >= 1.0 and not trading_state.did_buy:
                etf_price: int = int(current_price)

                trading_state.quantity = str(trading_state.deposit // etf_price)
                logger.info(
                    "Price threshold reached. placing buy order. etf_code=%s percent_change=%s price=%s deposit=%s quantity=%s",
                    trading_state.etf_code,
                    percent_change,
                    etf_price,
                    trading_state.deposit,
                    trading_state.quantity,
                )
                await asyncio.to_thread(self.client.buy_etf, trading_state.etf_code, trading_state.quantity)
                trading_state.did_buy = True
                stop_event.set()

        return trading_state
    
    async def _select_etf_with_biggest_volume(self, trading_state: TradingState) -> TradingState:
        """Select ETF with biggest trading volume and update trading_state.etf_code."""
        await self.ws_client.unregister_etf(trading_state.etf_code)
        trading_state.etf_code = self.client.get_biggest_etf_volume(self.etf_list, track_range=5)

        if trading_state.etf_code == "":
            logger.error("Failed to get ETF with biggest volume. etf_count=%s", len(self.etf_list))
            return trading_state
        logger.info("Selected ETF with biggest volume. etf_code=%s", trading_state.etf_code)
        return trading_state

    async def _run_trading_loop(self, trading_state: TradingState, stop_event: asyncio.Event) -> None:
        """Trading loop that continuously check ETF price while market is open."""
        await self.ws_client.unregister_etf(trading_state.etf_code)
        trading_state = await self._select_etf_with_biggest_volume(trading_state)
        # TODO: Wait when PRE_OPEN

        if trading_state.etf_code == "":
            logger.error("Failed to get ETF with biggest volume. etf_count=%s", len(self.etf_list))
            stop_event.set()
            return
        logger.info("Selected ETF with biggest volume. etf_code=%s", trading_state.etf_code)

        trading_state.deposit = self.client.check_deposit()
        logger.info("Checked current deposit. deposit=%s", trading_state.deposit)

        await self.ws_client.register_etf(trading_state.etf_code)

        while not stop_event.is_set():
            trading_state = await self._handle_etf_message_and_buy(trading_state, stop_event)

    async def run(self):
        logger.info("Connecting websocket for trading bot.")
        await self.ws_client.connect()
        login_msg = await self.ws_client.wait_for_login()
        logger.info("Received websocket login response. message=%s", login_msg)

        trading_state = TradingState()

        await self.ws_client.register_market_time()
        await self.ws_client.wait_for_register()

        stop_event = asyncio.Event()
        market_state_ready = asyncio.Event()
        market_task = asyncio.create_task(
            self._monitor_market_state(
                trading_state,
                stop_event,
                market_state_ready
            )
        )

        try:
            await market_state_ready.wait()

            if trading_state.market_state in [MarketState.PRE_OPEN, MarketState.OPEN]:
                # Start trading loop
                await self._run_trading_loop(trading_state, stop_event)
            else:
                stop_event.set()
        finally:
            stop_event.set()
            market_task.cancel()
            await asyncio.gather(market_task, return_exceptions=True)
