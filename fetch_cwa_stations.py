"""
fetch_cwa_stations.py
---------------------
負責抓取中央氣象署 (CWA) 自動氣象站最新即時觀測資料 (O-A0001-001)，
並進行數據清洗、驗證與標準化。
"""

import os
import sys
import json
import time
import requests
import urllib3
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

load_dotenv()

# CWA 自動氣象站觀測資料端點 (800+ 測站)
CWA_OBSERVATION_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001"
OUTPUT_OBSERVATION_FILE = "cwa_stations_latest.json"

_CACHE_DATA = None
_CACHE_TIMESTAMP = 0
CACHE_TTL = 300  # 快取 5 分鐘


def get_api_key() -> str:
    api_key = os.getenv("CWA_API_KEY", "").strip()
    return api_key if api_key else "CWA-55FDA6D3-A43C-4AE0-BB30-E62D5F684FB2"


def parse_float(val: Any) -> Optional[float]:
    """通用浮點數解析"""
    if val is None or val in ["", "X", "NA", "null", "-99", "-999", -99, -999]:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_temperature(val: Any) -> Optional[float]:
    """解析氣溫數值，合理範圍 -30°C ~ 60°C"""
    f = parse_float(val)
    if f is not None and -30 <= f <= 60:
        return round(f, 1)
    return None


def parse_coord(val: Any, is_lat: bool = True) -> Optional[float]:
    """解析台灣範圍經緯度 (緯度 20~27, 經度 118~123)"""
    f = parse_float(val)
    if f is None:
        return None
    if is_lat and 20.0 <= f <= 27.5:
        return round(f, 5)
    if not is_lat and 117.0 <= f <= 123.5:
        return round(f, 5)
    return None


def fetch_cwa_stations_data(force_refresh: bool = False) -> dict:
    """
    抓取並清洗全台自動氣象站即時觀測資料
    
    :param force_refresh: 是否強制忽略快取重新請求
    :return: 標準化測站清單字典
    """
    global _CACHE_DATA, _CACHE_TIMESTAMP
    now = time.time()
    
    if not force_refresh and _CACHE_DATA and (now - _CACHE_TIMESTAMP < CACHE_TTL):
        return _CACHE_DATA

    api_key = get_api_key()
    headers = {"Authorization": api_key}
    params = {"format": "JSON"}

    print(f"[INFO] 正在連線 CWA 即時觀測資料 API: {CWA_OBSERVATION_URL} ...")
    
    try:
        response = requests.get(
            CWA_OBSERVATION_URL,
            headers=headers,
            params=params,
            timeout=15,
            verify=False
        )
        response.raise_for_status()
        raw_json = response.json()
        
        station_list = raw_json.get("records", {}).get("Station", [])
        clean_stations = []
        
        for st in station_list:
            station_id = st.get("StationId")
            station_name = st.get("StationName")
            
            geo = st.get("GeoInfo", {})
            coords = geo.get("Coordinates", [])
            lat, lon = None, None
            
            for c in coords:
                if c.get("CoordinateName") == "WGS84":
                    lat = parse_coord(c.get("StationLatitude"), is_lat=True)
                    lon = parse_coord(c.get("StationLongitude"), is_lat=False)
                    break
            
            if (lat is None or lon is None) and coords:
                lat = parse_coord(coords[0].get("StationLatitude"), is_lat=True)
                lon = parse_coord(coords[0].get("StationLongitude"), is_lat=False)
                
            county = geo.get("CountyName") or ""
            town = geo.get("TownName") or ""
            
            obs = st.get("WeatherElement", {})
            air_temp = parse_temperature(obs.get("AirTemperature"))
            humidity = parse_float(obs.get("RelativeHumidity"))
            wind_speed = parse_float(obs.get("WindSpeed"))
            weather_desc = obs.get("Weather") or "晴"
            
            obs_time = st.get("ObsTime", {}).get("DateTime") or time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 必須具備有效座標與有效溫度
            if lat is not None and lon is not None and air_temp is not None:
                clean_stations.append({
                    "station_id": station_id,
                    "station_name": station_name,
                    "county": county,
                    "town": town,
                    "lat": lat,
                    "lon": lon,
                    "temperature_c": air_temp,
                    "humidity_percent": humidity,
                    "wind_speed_mps": wind_speed,
                    "weather": weather_desc,
                    "observed_at": obs_time
                })

        result = {
            "source": "CWA OpenData (O-A0001-001)",
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(clean_stations),
            "stations": clean_stations
        }
        
        _CACHE_DATA = result
        _CACHE_TIMESTAMP = now
        
        with open(OUTPUT_OBSERVATION_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        print(f"[SUCCESS] 成功獲取並清洗 {len(clean_stations)} 個自動氣象站觀測數據！")
        return result

    except Exception as e:
        print(f"[ERROR] 抓取氣象站觀測數據失敗: {e}")
        if _CACHE_DATA:
            return _CACHE_DATA
        raise


def get_stations_geojson() -> dict:
    """轉換為標準 GeoJSON FeatureCollection 格式"""
    data = fetch_cwa_stations_data()
    features = []
    
    for s in data.get("stations", []):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [s["lon"], s["lat"]]
            },
            "properties": {
                "station_id": s["station_id"],
                "station_name": s["station_name"],
                "county": s["county"],
                "town": s["town"],
                "temperature_c": s["temperature_c"],
                "humidity_percent": s["humidity_percent"],
                "wind_speed_mps": s["wind_speed_mps"],
                "weather": s.get("weather", ""),
                "observed_at": s["observed_at"]
            }
        })
        
    return {
        "type": "FeatureCollection",
        "updated_at": data.get("updated_at"),
        "features": features
    }


if __name__ == "__main__":
    print("=" * 50)
    print("[步驟 5] 測試抓取全台即時氣象站觀測資料")
    print("=" * 50)
    data = fetch_cwa_stations_data(force_refresh=True)
    print(f"有效測站總數: {data['count']}")
    if data['stations']:
        print("\n前 5 個測站範例：")
        for s in data['stations'][:5]:
            print(f" - [{s['station_id']}] {s['station_name']} ({s['county']}{s['town']}): {s['temperature_c']}°C, 濕度:{s['humidity_percent']}%, 風速:{s['wind_speed_mps']}m/s")
