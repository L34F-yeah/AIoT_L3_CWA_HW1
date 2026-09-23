"""
parse_weather.py
----------------
負責解析 CWA 氣象預報原始 JSON 資料，萃取各區域/縣市逐日的最高溫 (MaxT)、最低溫 (MinT) 與天氣概況。
"""

import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# 強制 stdout 使用 UTF-8 編碼以相容 Windows 終端機
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# 台灣各大分區與所屬縣市對照表
REGION_MAPPING = {
    "北部地區": ["基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "苗栗縣"],
    "中部地區": ["臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市", "嘉義縣"],
    "南部地區": ["臺南市", "高雄市", "屏東縣"],
    "東北部地區": ["宜蘭縣"],
    "東部地區": ["花蓮縣"],
    "東南部地區": ["臺東縣"],
    "離島地區": ["澎湖縣", "金門縣", "連江縣"]
}


def safe_float(val: Any) -> Optional[float]:
    """安全轉換浮點數，過濾無效值"""
    if val is None or val in ["", "NA", "null", "-99", "-999"]:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_cwa_json(raw_data: dict) -> List[Dict[str, Any]]:
    """
    解析 CWA 未來一週天氣預報 JSON
    
    :param raw_data: CWA 原始 JSON dict
    :return: 結構化後的各縣市逐日預報清單
    """
    records = raw_data.get("records", {})
    locations_wrapper = records.get("Locations", []) or records.get("locations", [])
    
    if not locations_wrapper:
        raise ValueError("找不到 Locations 欄位，請確認資料結構！")
        
    locations = locations_wrapper[0].get("Location", []) or locations_wrapper[0].get("location", [])
    
    parsed_results = []

    for loc in locations:
        loc_name = loc.get("LocationName") or loc.get("locationName")
        if not loc_name:
            continue
            
        weather_elements = loc.get("WeatherElement", []) or loc.get("weatherElement", [])
        
        # 暫存每日的時間區段數據: { "YYYY-MM-DD": { "max_temps": [], "min_temps": [], "weathers": [] } }
        daily_buckets: Dict[str, Dict[str, list]] = {}
        
        for el in weather_elements:
            el_name = el.get("ElementName") or el.get("elementName")
            times = el.get("Time", []) or el.get("time", [])
            
            for t in times:
                start_time_str = t.get("StartTime") or t.get("startTime") or ""
                if not start_time_str:
                    continue
                date_key = start_time_str.split("T")[0]
                
                if date_key not in daily_buckets:
                    daily_buckets[date_key] = {"max_temps": [], "min_temps": [], "weathers": []}
                
                element_vals = t.get("ElementValue", []) or t.get("elementValue", [])
                if not element_vals:
                    continue
                val_dict = element_vals[0]
                
                # 判斷元素類型
                if el_name in ["最高溫度", "MaxT", "MaxTemperature"]:
                    temp_val = safe_float(val_dict.get("MaxTemperature") or val_dict.get("value"))
                    if temp_val is not None:
                        daily_buckets[date_key]["max_temps"].append(temp_val)
                        
                elif el_name in ["最低溫度", "MinT", "MinTemperature"]:
                    temp_val = safe_float(val_dict.get("MinTemperature") or val_dict.get("value"))
                    if temp_val is not None:
                        daily_buckets[date_key]["min_temps"].append(temp_val)
                        
                elif el_name in ["天氣現象", "Wx", "Weather"]:
                    wx_val = val_dict.get("Weather") or val_dict.get("value")
                    if wx_val:
                        daily_buckets[date_key]["weathers"].append(wx_val)

        # 整理出每日一筆的預報
        for data_date, bucket in sorted(daily_buckets.items()):
            max_t = max(bucket["max_temps"]) if bucket["max_temps"] else None
            min_t = min(bucket["min_temps"]) if bucket["min_temps"] else None
            weather_desc = bucket["weathers"][0] if bucket["weathers"] else "晴到多雲"
            
            # 若最低溫高於最高溫進行修正保護
            if max_t is not None and min_t is not None and min_t > max_t:
                min_t, max_t = max_t, min_t
                
            parsed_results.append({
                "regionName": loc_name,
                "dataDate": data_date,
                "minT": min_t,
                "maxT": max_t,
                "weather": weather_desc
            })

    # 同時計算六大分區的聚合數據 (方便作業規範中的分區查詢)
    regional_results = generate_regional_aggregates(parsed_results)
    all_results = parsed_results + regional_results
    
    return all_results


def generate_regional_aggregates(county_forecasts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """依據六大分區對照表，計算各大分區的每日平均最低/最高溫"""
    regional_data = []
    
    # 整理為: { (region_group, date): { "min_list": [], "max_list": [] } }
    grouped: Dict[tuple, Dict[str, list]] = {}
    
    county_to_region = {}
    for region_group, counties in REGION_MAPPING.items():
        for c in counties:
            county_to_region[c] = region_group
            
    for item in county_forecasts:
        county = item["regionName"]
        region_group = county_to_region.get(county)
        if not region_group:
            continue
            
        key = (region_group, item["dataDate"])
        if key not in grouped:
            grouped[key] = {"min_list": [], "max_list": [], "weathers": []}
            
        if item["minT"] is not None:
            grouped[key]["min_list"].append(item["minT"])
        if item["maxT"] is not None:
            grouped[key]["max_list"].append(item["maxT"])
        if item.get("weather"):
            grouped[key]["weathers"].append(item["weather"])
            
    for (region_group, data_date), data in grouped.items():
        avg_min = round(sum(data["min_list"]) / len(data["min_list"]), 1) if data["min_list"] else None
        avg_max = round(sum(data["max_list"]) / len(data["max_list"]), 1) if data["max_list"] else None
        weather = data["weathers"][0] if data["weathers"] else "多雲"
        
        regional_data.append({
            "regionName": region_group,
            "dataDate": data_date,
            "minT": avg_min,
            "maxT": avg_max,
            "weather": weather
        })
        
    return regional_data


def parse_and_save(input_file: str = "cwa_raw_forecast.json", output_file: str = "cwa_parsed_forecast.json") -> List[Dict[str, Any]]:
    """讀取暫存的 raw JSON，解析並輸出清洗後的 JSON 檔案"""
    with open(input_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    results = parse_cwa_json(raw_data)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"[SUCCESS] 成功解析 {len(results)} 筆預報資料，已輸出至: {output_file}")
    return results


if __name__ == "__main__":
    print("=" * 50)
    print("[步驟 2] 測試解析 CWA JSON 氣象資料")
    print("=" * 50)
    
    results = parse_and_save()
    
    # 預覽台北市與北部地區的解析成果
    sample_items = [r for r in results if r["regionName"] in ["臺北市", "北部地區"]]
    print(f"\n[SAMPLE] 預覽部分解析成果 (共 {len(sample_items)} 筆)：")
    for item in sample_items[:6]:
        print(f" - 地區: {item['regionName']:<6} | 日期: {item['dataDate']} | 最低溫: {item['minT']}°C | 最高溫: {item['maxT']}°C | 天氣: {item['weather']}")
