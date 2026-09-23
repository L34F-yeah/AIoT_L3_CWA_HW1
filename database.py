"""
database.py
-----------
負責管理 SQLite 資料庫 (data.db)，包含建立 TemperatureForecasts 資料表、
批次寫入氣象預報數據，以及提供標準 SQL 查詢介面。
"""

import sys
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Tuple
from parse_weather import parse_and_save

# 強制 stdout 使用 UTF-8 編碼以相容 Windows 終端機
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

DB_PATH = "data.db"


def get_db_connection() -> sqlite3.Connection:
    """取得資料庫連線並設定 row_factory 為 sqlite3.Row 便於字典存取"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """
    初始化建立 TemperatureForecasts 資料表
    符合作業規範設計：
    CREATE TABLE TemperatureForecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        regionName TEXT,
        dataDate TEXT,
        minT REAL,
        maxT REAL,
        weather TEXT
    );
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS TemperatureForecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                regionName TEXT NOT NULL,
                dataDate TEXT NOT NULL,
                minT REAL,
                maxT REAL,
                weather TEXT
            );
        """)
        # 建立索引以加速區域與日期查詢
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_region_date 
            ON TemperatureForecasts (regionName, dataDate);
        """)
        conn.commit()
    print(f"[DB] 資料表 TemperatureForecasts 初始化完成！(資料庫檔案: {DB_PATH})")


def save_forecast_data(forecast_list: List[Dict[str, Any]]):
    """
    將解析後的預報資料批次寫入資料庫 (先清空舊資料再批次寫入)
    
    :param forecast_list: 由 parse_weather 解析出的預報清單
    """
    if not forecast_list:
        print("[WARN] 無可寫入的預報資料！")
        return

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # 清空舊資料以維持最新快照
        cursor.execute("DELETE FROM TemperatureForecasts;")
        
        insert_sql = """
            INSERT INTO TemperatureForecasts (regionName, dataDate, minT, maxT, weather)
            VALUES (:regionName, :dataDate, :minT, :maxT, :weather);
        """
        cursor.executemany(insert_sql, forecast_list)
        conn.commit()
        
    print(f"[DB SUCCESS] 成功寫入 {len(forecast_list)} 筆預報資料至資料庫！")


def get_all_regions() -> List[str]:
    """查詢所有可用地區名稱 (SELECT DISTINCT regionName)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT regionName FROM TemperatureForecasts ORDER BY id ASC;")
        rows = cursor.fetchall()
        return [row["regionName"] for row in rows]


def get_forecast_by_region(region_name: str) -> pd.DataFrame:
    """
    查詢特定地區的未來一週預報資料，並回傳 Pandas DataFrame
    
    :param region_name: 地區名稱 (如 '北部地區' 或 '臺北市')
    :return: 包含日期、最低溫、最高溫、天氣現象的 DataFrame
    """
    query = """
        SELECT 
            dataDate AS 日期,
            minT AS 最低溫,
            maxT AS 最高溫,
            weather AS 天氣現象
        FROM TemperatureForecasts
        WHERE regionName = ?
        ORDER BY dataDate ASC;
    """
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query, conn, params=(region_name,))
    return df


if __name__ == "__main__":
    print("=" * 50)
    print("[步驟 3] 測試建立 SQLite 資料庫與存入資料")
    print("=" * 50)
    
    # 1. 初始化資料庫
    init_database()
    
    # 2. 取得解析後資料並寫入 DB
    parsed_data = parse_and_save()
    save_forecast_data(parsed_data)
    
    # 3. 測試 SQL 查詢功能
    regions = get_all_regions()
    print(f"\n[QUERY] 資料庫中涵蓋的地區清單 (共 {len(regions)} 個)：")
    print("六大分區:", [r for r in regions if "地區" in r])
    print("部分縣市:", [r for r in regions if "地區" not in r][:8])
    
    # 4. 測試查詢特定區域 (例如: 中部地區 與 臺北市)
    for test_region in ["中部地區", "臺北市"]:
        print(f"\n[QUERY RESULT] 查詢『{test_region}』的一週天氣預報：")
        df_result = get_forecast_by_region(test_region)
        print(df_result.to_string(index=False))
