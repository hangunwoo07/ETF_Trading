from dotenv import load_dotenv
import os
from typing import Optional, List, Dict
from KiwoomClient import KiwoomClient
from KiwoomWebsocket import KiwoomWebsocketClient
import asyncio


async def main():
    load_dotenv()
    app_key: Optional[str] = os.getenv("APP_KEY")
    secret_key: Optional[str] = os.getenv("SECRET_KEY")
    is_mock: bool = os.getenv("IS_MOCK") == "True"

    if not app_key or not secret_key:
        raise RuntimeError("APP_KEY and SECRET_KEY must be set in .env file")

    etf_list: List[str] = [
        "091160",
        "091180",
        "102960",
        "117460",
        "244580",
        "305720",
        "102970",
        "117700",
        "300950",
        "266390",
        "266360",
        "140710",
        "091170",
        "117680",
        "266410",
        "445290",
        "449450",
        "466920",
        "487240",
        "0115D0",
        "0148J0",
    ]
    client = KiwoomClient()
    ws_client = KiwoomWebsocketClient(is_mock=is_mock, access_token=client.access_token)

    await ws_client.connect()
    await ws_client.receive_message()

    await ws_client.register_market_time()
    market_time_msg: Optional[Dict] = await ws_client.receive_message()

    if market_time_msg is None:
        raise RuntimeError("Failed to receive market time message")
    
    # First loop of program
    if market_time_msg.get("data")[0].get("values").get("215") == "0":  # type: ignore
        print("Preparing for market open...")
        
        etf_code: str = client.get_biggest_etf_volume(etf_list, track_range=5)
        print(f"ETF with biggest volume: {etf_code}")

        deposit: int = client.check_deposit()
        print(f"Current deposit: {deposit}")

        while True:
            market_open_msg: Optional[Dict] = await ws_client.receive_message() # Market open message

            if market_open_msg is None or market_time_msg.get("data")[0].get("type") != "0s": # type: ignore
                continue
            elif market_time_msg.get("data")[0].get("values").get("215") == "3": # type: ignore
                print("Market opened!")
                break
        
        # Market open!
        await ws_client.register_etf(etf_code)
        await ws_client.receive_message() # Register message

        while True:
            did_buy: bool = False
            quantity: str = "0"

            msg: Optional[Dict] = await ws_client.receive_message()
            if msg is None:
                continue
            data: List = msg.get("data", [])
            data_type = data[0].get("type")

            if data_type == "0B":
                # ETF price change message
                percent_change: str = data[0].get("values").get("12")

                if percent_change[0] == "+":
                    if float(percent_change[1:]) >= 1:
                        etf_price: int = int(data[0].get("values").get("10"))
                        print(f"Price increased by {percent_change}, placing buy order...")
                        quantity: str = str(deposit // etf_price)
                        client.buy_etf(etf_code, quantity=quantity)
                        did_buy = True
                        break
            elif data_type == "0s":
                # Market time message
                if data[0].get("values").get("215") == "4":
                    print("Market closed!")
                    break
        
        # Main loop of program, runs 24/7
        while True:
            await ws_client.unregister_etf(etf_code) # Unregister ETF that was bought in market before
            await ws_client.receive_message() # Unregister message

            while True:
                await ws_client.receive_message() # Wait until market open message is received

                if market_time_msg.get("data")[0].get("values").get("215") == "0": # type: ignore
                    print("Preparing for market open...")
                    break
            
            new_etf_code: str = client.get_biggest_etf_volume(etf_list, track_range=5)
            print(f"ETF with biggest volume: {new_etf_code}")

            deposit = client.check_deposit()
            print(f"Current deposit: {deposit}")

            while True:
                market_open_msg: Optional[Dict] = await ws_client.receive_message() # Market open message

                if market_open_msg is None or market_time_msg.get("data")[0].get("type") != "0s": # type: ignore
                    continue
                elif market_time_msg.get("data")[0].get("values").get("215") == "3": # type: ignore
                    print("Market opened!")
                    break
            
            # Market open!
            if did_buy:
                client.sell_etf(etf_code, quantity)
                print(f"Placed sell order for {quantity} shares of {etf_code}")
            
            etf_code = new_etf_code

            await ws_client.register_etf(etf_code)
            await ws_client.receive_message() # Register message

            while True:
                did_buy = False
                quantity = "0"
                msg: Optional[Dict] = await ws_client.receive_message()
                if msg is None:
                    continue
                data: List = msg.get("data", [])
                data_type = data[0].get("type")

                if data_type == "0B":
                    # ETF price change message
                    percent_change: str = data[0].get("values").get("12")

                    if percent_change[0] == "+":
                        if float(percent_change[1:]) >= 1:
                            etf_price: int = int(data[0].get("values").get("10"))
                            print(f"Price increased by {percent_change}, placing buy order...")
                            quantity: str = str(deposit // etf_price)
                            client.buy_etf(etf_code, quantity=quantity)
                            did_buy = True
                            break
                elif data_type == "0s":
                    # Market time message
                    if data[0].get("values").get("215") == "4":
                        print("Market closed!")
                        break


if __name__ == "__main__":
    asyncio.run(main())
