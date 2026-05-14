from dotenv import load_dotenv
from typing import List, Optional
import logging
import os
import requests
import time


logger = logging.getLogger(__name__)


class KiwoomClient:
    def __init__(self):
        load_dotenv()
        self.app_key: Optional[str] = os.getenv("APP_KEY")
        self.secret_key: Optional[str] = os.getenv("SECRET_KEY")
        self.is_mock: bool = os.getenv("IS_MOCK") == "True"
        self.base_url: str = 'https://api.kiwoom.com' if not self.is_mock else 'https://mockapi.kiwoom.com'
        
        if not self.app_key or not self.secret_key:
            raise ValueError("APP_KEY and SECRET_KEY must be set in environment variables.")
        
        self.access_token: str = self.get_access_token()
    
    def get_access_token(self) -> str:
        url = f"{self.base_url}/oauth2/token"

        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.secret_key
        }

        res = requests.post(url, json=payload, timeout=10)
        data = res.json()

        if data.get("return_code") != 0:
            logger.error("Failed to fetch access token. response=%s", data)
            raise RuntimeError(f"Error when fetching access token: \n{data}")
        
        logger.info("Fetched Kiwoom access token.")
        return data["token"]

    def check_deposit(self) -> int:
        url = f"{self.base_url}/api/dostk/acnt"
        
        headers = {
            "api-id": "kt00001",
            "authorization": f"Bearer {self.access_token}",
        }

        payload = {
            "qry_tp": "2"
        }

        res = requests.post(url, headers=headers, json=payload, timeout=10)
        data = res.json()

        if data.get("return_code") != 0:
            logger.error("Failed to check deposit. response=%s", data)
            return -1
        
        deposit = int(data.get("entr"))
        logger.info("Checked deposit from Kiwoom API. deposit=%s", deposit)
        return deposit

    def get_biggest_etf_volume(self, etf_list: List[str], track_range: int) -> str:
        url = f"{self.base_url}/api/dostk/etf"

        headers = {
            "api-id": "ka40003",
            "authorization": f"Bearer {self.access_token}",
        }

        max_volume: int = -1
        max_volume_etf: str = etf_list[0]

        for etf_code in etf_list:
            payload = {
                "stk_cd": etf_code
            }

            res = requests.post(url, headers=headers, json=payload, timeout=10)
            data = res.json()

            if data.get("return_code") != 0:
                logger.error("Failed to fetch ETF data. etf_code=%s response=%s", etf_code, data)
                raise RuntimeError(f"Error fetching data for {etf_code}: \n{data}")

            daily_data_list: List = data.get("etfdaly_trnsn", [])
            
            volume = sum(int(item.get("acc_trde_prica", 0)) for item in daily_data_list[:track_range])
            logger.info(
                "Calculated ETF recent volume. etf_code=%s track_range=%s volume=%s",
                etf_code,
                track_range,
                volume,
            )

            if volume > max_volume:
                max_volume = volume
                max_volume_etf = etf_code
            
            time.sleep(1)

        return max_volume_etf
    
    def buy_etf(self, etf_code: str, quantity: str):
        url = f"{self.base_url}/api/dostk/ordr"

        headers = {
            "api-id": "kt10000",
            "authorization": f"Bearer {self.access_token}",
        }

        payload = {
            "dmst_stex_tp": "KRX",
            "stk_cd": etf_code,
            "ord_qty": quantity,
            "trde_tp": "3", # 시장가 매수
        }
        
        res = requests.post(url, headers=headers, json=payload, timeout=10)

        data = res.json()

        if data.get("return_code") != 0:
            logger.error(
                "Failed to place buy order. etf_code=%s quantity=%s response=%s",
                etf_code,
                quantity,
                data,
            )
            return

        logger.info("Placed buy order successfully. etf_code=%s quantity=%s response=%s", etf_code, quantity, data)
    
    def sell_etf(self, etf_code: str, quantity: str) -> str:
        url = f"{self.base_url}/api/dostk/ordr"

        headers = {
            "api-id": "kt10001",
            "authorization": f"Bearer {self.access_token}",
        }

        payload = {
            "dmst_stex_tp": "KRX",
            "stk_cd": etf_code,
            "ord_qty": quantity,
            "trde_tp": "3", # 시장가 매도
        }

        res = requests.post(url, headers=headers, json=payload, timeout=10)

        data = res.json()

        if data.get("return_code") != 0:
            logger.error(
                "Failed to place sell order. etf_code=%s quantity=%s response=%s",
                etf_code,
                quantity,
                data,
            )
            return f"Error placing order: \n{data}"

        logger.info("Placed sell order successfully. etf_code=%s quantity=%s response=%s", etf_code, quantity, data)
        return f"Order placed successfully: \n{data}"
