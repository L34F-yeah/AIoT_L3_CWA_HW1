"""
fetch_weather.py
----------------
負責透過中央氣象署 OpenData API (F-D0047-091: 台灣未來一週天氣預報) 抓取氣象資料。
"""

import os
import sys
import json
import requests
import urllib3
from dotenv import load_dotenv

# 忽略 SSL 不安全連線警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 強制 stdout 使用 UTF-8 編碼以相容 Windows 終端機
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# 載入 .env 環境變數
load_dotenv()

# CWA API 端點 (F-D0047-091: 台灣各縣市未來1週天氣預報)
CWA_API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-091"
DEFAULT_OUTPUT_FILE = "cwa_raw_forecast.json"


def get_api_key() -> str:
    """取得 CWA API Key，優先讀取環境變數，若無則使用預設金鑰"""
    api_key = os.getenv("CWA_API_KEY", "").strip()
    if not api_key:
        api_key = "CWA-55FDA6D3-A43C-4AE0-BB30-E62D5F684FB2"
    return api_key


def fetch_weather_data(api_key: str = None, save_to_file: bool = True) -> dict:
    """
    呼叫 CWA API 獲取未來一週天氣預報資料
    
    :param api_key: CWA API 授權碼
    :param save_to_file: 是否將原始 JSON 寫入檔案備份
    :return: 解析後的 JSON dict
    """
    if not api_key:
        api_key = get_api_key()

    headers = {
        "Authorization": api_key
    }
    params = {
        "format": "JSON"
    }

    print(f"[INFO] 正在請求 CWA API: {CWA_API_URL} ...")
    
    try:
        response = requests.get(
            CWA_API_URL,
            headers=headers,
            params=params,
            timeout=15,
            verify=False
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("success") == "true":
            raise ValueError(f"API 回傳失敗訊息: {data.get('message', '未知錯誤')}")
            
        print("[SUCCESS] 成功取得 CWA 氣象資料！")
        
        if save_to_file:
            with open(DEFAULT_OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[SAVE] 原始資料已暫存至: {DEFAULT_OUTPUT_FILE}")
            
        return data

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 網路請求錯誤: {e}")
        raise
    except Exception as e:
        print(f"[ERROR] 資料處理異常: {e}")
        raise


if __name__ == "__main__":
    print("=" * 50)
    print("[步驟 1] 測試抓取 CWA 一週天氣預報資料")
    print("=" * 50)
    
    weather_data = fetch_weather_data()
    
    # 提取各縣市/地區清單
    try:
        locations_container = weather_data.get("records", {}).get("Locations", [])
        if locations_container:
            locations = locations_container[0].get("Location", [])
        else:
            locations = weather_data.get("records", {}).get("locations", [{}])[0].get("location", [])
            
        print(f"\n[RESULT] 成功獲取 {len(locations)} 個縣市/地區的預報資料：")
        for loc in locations:
            loc_name = loc.get("LocationName") or loc.get("locationName")
            print(f" - 📍 {loc_name}")
    except Exception as err:
        print(f"[WARN] 剖析預覽清單時發生例外: {err}")
