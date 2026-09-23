"""
backend_api.py
--------------
FastAPI 後端 API 服務
提供 CWA 即時氣象站觀測資料之 RESTful JSON 與 GeoJSON 端點。
"""

import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fetch_cwa_stations import fetch_cwa_stations_data, get_stations_geojson

# 強制 stdout 使用 UTF-8 編碼
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

app = FastAPI(
    title="CWA Taiwan Weather Station API",
    description="台灣中央氣象署即時自動氣象站觀測數據 API",
    version="1.0.0"
)

# 設定 CORS 允許跨域請求 (供前端 Leaflet / Windy 呼叫)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", summary="健康檢查端點")
async def health_check():
    """確認後端服務運作狀態"""
    return {
        "status": "ok",
        "service": "CWA Temperature Backend Service",
        "cwa_cache_status": "fresh"
    }


@app.get("/api/temperature/latest", summary="取得最新全台氣象站氣溫觀測資料")
async def get_latest_temperature(force: bool = False):
    """回傳所有有效氣象站即時氣溫、濕度、風速數據"""
    try:
        data = fetch_cwa_stations_data(force_refresh=force)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取得氣象資料失敗: {str(e)}")


@app.get("/api/temperature/geojson", summary="取得 GeoJSON 格式氣象站圖層")
async def get_temperature_geojson():
    """回傳符合 Leaflet / GIS 規範之 FeatureCollection GeoJSON"""
    try:
        geojson = get_stations_geojson()
        return geojson
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"轉換 GeoJSON 失敗: {str(e)}")


@app.get("/api/temperature/stations/{station_id}", summary="查詢單一氣象站詳細資訊")
async def get_station_detail(station_id: str):
    """依 Station ID 查詢單一測站資料"""
    data = fetch_cwa_stations_data()
    for s in data.get("stations", []):
        if s["station_id"] == station_id:
            return s
    raise HTTPException(status_code=404, detail=f"找不到測站代碼: {station_id}")


if __name__ == "__main__":
    import uvicorn
    print("[INFO] 正在啟動 FastAPI 後端服務: http://127.0.0.1:8000 ...")
    uvicorn.run("backend_api:app", host="127.0.0.1", port=8000, reload=False)
