"""
app.py
------
Streamlit 氣象預報互動式 Web 應用程式 (Taiwan Weather Forecast Dashboard)
整合 SQLite 資料庫、即時氣象圖表、數據明細與台灣氣溫地圖視覺化。
"""

import os
import sys
import datetime
import sqlite3
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

# 強制 stdout 使用 UTF-8 編碼
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# 匯入後端處理模組
from fetch_weather import fetch_weather_data
from parse_weather import parse_cwa_json
from database import init_database, save_forecast_data, get_all_regions, get_forecast_by_region, DB_PATH

# 台灣主要地區座標 (供地圖視覺化使用)
REGION_COORDINATES = {
    "北部地區": (25.0375, 121.5637),
    "中部地區": (24.1477, 120.6736),
    "南部地區": (22.9997, 120.2270),
    "東北部地區": (24.7570, 121.7530),
    "東部地區": (23.9912, 121.6196),
    "東南部地區": (22.7583, 121.1444),
    "離島地區": (23.5658, 119.5790),
    "臺北市": (25.0375, 121.5637),
    "新北市": (25.0116, 121.4657),
    "基隆市": (25.1276, 121.7392),
    "桃園市": (24.9936, 121.3010),
    "新竹市": (24.8138, 120.9675),
    "新竹縣": (24.8387, 121.0177),
    "苗栗縣": (24.5602, 120.8214),
    "臺中市": (24.1477, 120.6736),
    "彰化縣": (24.0518, 120.5161),
    "南投縣": (23.9609, 120.9719),
    "雲林縣": (23.7092, 120.4313),
    "嘉義市": (23.4800, 120.4491),
    "嘉義縣": (23.4518, 120.2555),
    "臺南市": (22.9997, 120.2270),
    "高雄市": (22.6273, 120.3014),
    "屏東縣": (22.5519, 120.5487),
    "宜蘭縣": (24.7570, 121.7530),
    "花蓮縣": (23.9912, 121.6196),
    "臺東縣": (22.7583, 121.1444),
    "澎湖縣": (23.5658, 119.5790),
    "金門縣": (24.4493, 118.3766),
    "連江縣": (26.1505, 119.9499),
}

# ----------------- 頁面基本配置 -----------------
st.set_page_config(
    page_title="Taiwan Weather Forecast | 台灣天氣預報",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 樣式提升 UI 美感
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #4B5563;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #F0FDF4 0%, #E0F2FE 100%);
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #E2E8F0;
    }
    .legend-box {
        display: flex;
        gap: 12px;
        align-items: center;
        flex-wrap: wrap;
        margin-top: 10px;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.85rem;
    }
    .legend-color {
        width: 14px;
        height: 14px;
        border-radius: 50%;
    }
</style>
""", unsafe_allow_html=True)


def ensure_database_loaded():
    """確保資料庫已初始化並載有資料，若無則自動執行抓取"""
    if not os.path.exists(DB_PATH):
        with st.spinner("📦 首次啟動：正在初始化資料庫並抓取最新氣象資料..."):
            sync_weather_pipeline()
    else:
        # 檢查資料表是否為空
        try:
            regions = get_all_regions()
            if not regions:
                sync_weather_pipeline()
        except Exception:
            sync_weather_pipeline()


def sync_weather_pipeline():
    """執行完整資料更新管線: CWA API -> 解析 -> 寫入 SQLite"""
    try:
        raw_data = fetch_weather_data(save_to_file=True)
        parsed_data = parse_cwa_json(raw_data)
        init_database()
        save_forecast_data(parsed_data)
        st.toast("✅ 氣象預報資料已成功同步更新！", icon="🎉")
        return True
    except Exception as e:
        st.error(f"❌ 同步氣象資料失敗: {e}")
        return False


def get_temp_color(temp: float) -> str:
    """依氣溫區間回傳標記顏色"""
    if temp < 20:
        return "#3B82F6"  # 藍色 (< 20°C 涼冷)
    elif temp < 25:
        return "#10B981"  # 綠色 (20-25°C 舒適)
    elif temp < 30:
        return "#F59E0B"  # 黃橙色 (25-30°C 溫暖)
    else:
        return "#EF4444"  # 紅色 (> 30°C 炎熱)


# 確保 DB 正常
ensure_database_loaded()

# ----------------- 側邊欄控制面板 -----------------
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1592210454359-9043f067919b?w=400&auto=format&fit=crop&q=80", use_container_width=True)
    st.title("⚙️ 預報控制面板")
    
    # 取得可用地區清單
    all_regions = get_all_regions()
    
    # 優先排序：六大分區置頂，接著是各縣市
    major_regions = [r for r in all_regions if "地區" in r]
    counties = [r for r in all_regions if "地區" not in r]
    ordered_regions = major_regions + counties
    
    # 預設選取「北部地區」
    default_index = ordered_regions.index("北部地區") if "北部地區" in ordered_regions else 0
    
    selected_region = st.selectbox(
        "📍 選擇預報地區：",
        options=ordered_regions,
        index=default_index,
        help="支援查詢台灣六大分區或個別縣市"
    )
    
    st.markdown("---")
    st.markdown("### 🔄 資料同步")
    if st.button("一鍵更新氣象局資料", use_container_width=True, type="primary"):
        with st.spinner("正在連線中央氣象署抓取最新資料..."):
            if sync_weather_pipeline():
                st.rerun()
                
    st.markdown("---")
    st.markdown("""
    **📚 專案資訊 (About)**
    - **課程作業**：HW10 Taiwan Weather Forecast
    - **資料來源**：[中央氣象署 OpenData (F-D0047-091)](https://opendata.cwa.gov.tw/)
    - **技術棧**：Streamlit, SQLite, Requests, Folium
    """)

# ----------------- 主介面展示 -----------------
st.markdown('<div class="main-header">🌦️ Taiwan Weather Forecast — 台灣天氣預報</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-header">即時查詢全台六大區域與各縣市未來一週天氣預報與氣溫走勢 • 目前查詢：<strong>{selected_region}</strong></div>', unsafe_allow_html=True)

# 查詢該地區之未來一週資料
df_forecast = get_forecast_by_region(selected_region)

if not df_forecast.empty:
    # 1. 頂部重點指標 (Metrics Cards)
    today_row = df_forecast.iloc[0]
    avg_week_max = df_forecast["最高溫"].mean()
    avg_week_min = df_forecast["最低溫"].mean()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label=f"📅 今日預報 ({today_row['日期']})",
            value=f"{today_row['天氣現象']}",
            help="當日代表性天氣現象"
        )
    with col2:
        st.metric(
            label="🌡️ 今日氣溫區間",
            value=f"{today_row['最低溫']}°C ~ {today_row['最高溫']}°C",
            delta=f"溫差 {round(today_row['最高溫'] - today_row['最低溫'], 1)}°C",
            delta_color="off"
        )
    with col3:
        st.metric(
            label="📈 一週平均最高溫",
            value=f"{avg_week_max:.1f} °C",
            delta=f"最高 {df_forecast['最高溫'].max():.1f}°C"
        )
    with col4:
        st.metric(
            label="📉 一週平均最低溫",
            value=f"{avg_week_min:.1f} °C",
            delta=f"最低 {df_forecast['最低溫'].min():.1f}°C",
            delta_color="inverse"
        )

    st.markdown("---")
    
    # 2. 雙欄佈局：折線圖 + 資料表格
    left_col, right_col = st.columns([3, 2])
    
    with left_col:
        st.subheader(f"📊 {selected_region} — 未來一週高低溫走勢圖")
        
        # 準備繪圖 DataFrame
        chart_df = df_forecast.copy()
        chart_df = chart_df.rename(columns={"最低溫": "最低氣溫 (°C)", "最高溫": "最高氣溫 (°C)"})
        chart_df = chart_df.set_index("日期")[["最高氣溫 (°C)", "最低氣溫 (°C)"]]
        
        # 繪製 Streamlit 折線圖
        st.line_chart(
            chart_df,
            color=["#EF4444", "#3B82F6"],  # 最高溫紅色、最低溫藍色
            height=360,
            use_container_width=True
        )
        
        st.caption("🔴 紅線：每日預測最高溫 | 🔵 藍線：每日預測最低溫")

    with right_col:
        st.subheader("📋 逐日詳細預報數據")
        
        # 格式化表格展示
        display_df = df_forecast.copy()
        display_df["平均溫 (°C)"] = ((display_df["最高溫"] + display_df["最低溫"]) / 2).round(1)
        
        # 調整欄位順序
        display_df = display_df[["日期", "天氣現象", "最低溫", "最高溫", "平均溫 (°C)"]]
        display_df.rename(columns={"最低溫": "最低溫 (°C)", "最高溫": "最高溫 (°C)"}, inplace=True)
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=360
        )

    st.markdown("---")
    
    # 3. 進階功能：台灣氣溫地圖視覺化 (Folium Map)
    st.subheader("🗺️ 全台各區平均氣溫地圖 (Taiwan Temperature Map)")
    st.write("點擊地圖上的各區標記可查看最新預測氣溫與天氣資訊：")
    
    # 取得全台所有地區當日/平均預報
    with sqlite3.connect(DB_PATH) as conn:
        all_df = pd.read_sql_query("""
            SELECT regionName, AVG((minT + maxT)/2) as avgTemp, MIN(minT) as minT, MAX(maxT) as maxT, weather
            FROM TemperatureForecasts
            GROUP BY regionName
        """, conn)
        
    # 建立 Folium 地圖 (中心設於台灣)
    m = folium.Map(location=[23.7, 120.9], zoom_start=7, tiles="OpenStreetMap")
    
    for _, row in all_df.iterrows():
        reg = row["regionName"]
        if reg in REGION_COORDINATES:
            lat, lon = REGION_COORDINATES[reg]
            avg_temp = round(row["avgTemp"], 1) if row["avgTemp"] is not None else 25.0
            color = get_temp_color(avg_temp)
            
            popup_html = f"""
            <div style="font-family: sans-serif; font-size: 13px; line-height: 1.5; min-width: 140px;">
                <h4 style="margin: 0 0 6px 0; color: #1E3A8A;">📍 {reg}</h4>
                <b>平均溫度：</b> {avg_temp} °C<br/>
                <b>最低 ~ 最高：</b> {row['minT']}°C ~ {row['maxT']}°C<br/>
                <b>代表天氣：</b> {row['weather']}
            </div>
            """
            
            folium.CircleMarker(
                location=[lat, lon],
                radius=10 if "地區" in reg else 7,
                color="#FFFFFF",
                weight=1.5,
                fill=True,
                fill_color=color,
                fill_opacity=0.85,
                tooltip=f"{reg}: {avg_temp}°C ({row['weather']})",
                popup=folium.Popup(popup_html, max_width=200)
            ).add_to(m)
            
    # 顯示地圖
    st_folium(m, width=None, height=420, returned_objects=[])
    
    # 圖例說明
    st.markdown("""
    <div class="legend-box">
        <span style="font-weight: 600; font-size: 0.9rem;">🎨 氣溫色階圖例：</span>
        <div class="legend-item"><div class="legend-color" style="background:#3B82F6;"></div> &lt; 20°C 涼冷</div>
        <div class="legend-item"><div class="legend-color" style="background:#10B981;"></div> 20 – 25°C 舒適</div>
        <div class="legend-item"><div class="legend-color" style="background:#F59E0B;"></div> 25 – 30°C 溫暖</div>
        <div class="legend-item"><div class="legend-color" style="background:#EF4444;"></div> &gt; 30°C 炎熱</div>
    </div>
    """, unsafe_allow_html=True)

else:
    st.warning("⚠️ 目前資料庫中無資料，請點擊左側側邊欄的「一鍵更新氣象局資料」按鈕！")
