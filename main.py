from dotenv import load_dotenv
import os
from typing import Optional, List
from KiwoomClient import KiwoomClient
from KiwoomWebsocket import KiwoomWebsocketClient


def main():
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

    etf_code: str = client.get_biggest_etf_volume(etf_list, track_range=5)
    print(f"ETF with biggest volume: {etf_code}")

    deposit: int = client.check_deposit()
    print(f"Current deposit: {deposit}")

    ws_client = KiwoomWebsocketClient(is_mock=is_mock, access_token=client.access_token)
    await ws_client.connect()
    await ws_client.receive_message() # LOGIN message

    await ws_client.register_etf(etf_code)
    await ws_client.receive_message() # Register message

    while True:
        msg = await ws_client.receive_message()
        data: List = msg.get("data", [])
        percent_change: str = data[0].get("values").get("12")

        if percent_change[0] == "+":
            if float(percent_change[1:]) >= 1:
                etf_price: int = int(data[0].get("values").get("10"))
                print(f"Price increased by {percent_change}, placing buy order...")
                client.buy_etf(etf_code, quantity=str(deposit // etf_price))

                break



if __name__ == "__main__":
    # asyncio.run(main())
    main()