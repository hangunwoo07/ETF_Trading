from datetime import datetime, time
import exchange_calendars as xcals
import pandas as pd


class MarketTimeChecker:
    """
    Class to check if the market is currently open based on datetime and holidays.
    """
    def __init__(self):
        self.calendar = xcals.get_calendar("XKRX")
        self.date = datetime.now().date()
        self.now = datetime.now().time()
        self.market_open_time = time(9, 0)
        self.market_close_time = time(15, 30)
    
    def is_trading_day(self) -> bool:
        return self.calendar.is_session(pd.Timestamp(self.date))
    
    def is_market_open(self) -> bool:
        if not self.is_trading_day():
            return False
        
        return self.market_open_time <= self.now <= self.market_close_time
    
    def time_to_prepare(self) -> bool:
        """Check if it's time to prepare for market open (30 minutes before)"""
        if not self.is_trading_day():
            return False
        
        return time(8, 30) <= self.now < self.market_open_time


def main():
    market_time_checker = MarketTimeChecker()
    print(f"Is today a trading day? {'Yes' if market_time_checker.is_trading_day() else 'No'}")
    print(f"Is the market open? {'Yes' if market_time_checker.is_market_open() else 'No'}")


if __name__ == "__main__":
    main()