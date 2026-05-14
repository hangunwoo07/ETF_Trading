from dotenv import load_dotenv
import os
from typing import Optional, List
from Supervisor import Supervisor
from logging_config import setup_logging
import asyncio


async def main():
    setup_logging()
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
    
    supervisor = Supervisor(is_mock=is_mock, etf_list=etf_list)

    await supervisor.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
