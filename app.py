"""
app.py
------
Streamlit 氣象預報互動式 Web 應用程式 (Taiwan Weather Forecast Dashboard)
整合 SQLite 資料庫、一週天氣預報走勢、數據明細與全台 800+ 氣象站即時氣溫地圖視覺化。
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
from fetch_cwa_stations import fetch_cwa_stations_data

# 台灣主要地區座標 (供分區地圖使用)
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
    page_title="Taiwan Weather Forecast & Real-time Map",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 樣式
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
        margin-bottom: 1.2rem;
    }
    .legend-box {
        display: flex;
        gap: 14px;
        align-items: center;
        flex-wrap: wrap;
        margin-top: 10px;
        padding: 8px 12px;
        background: #F8FAFC;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
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
    """確保預報資料庫已初始化"""
    if not os.path.exists(DB_PATH):
        sync_forecast_pipeline()
    else:
        try:
            regions = get_all_regions()
            if not regions:
                sync_forecast_pipeline()
        except Exception:
            sync_forecast_pipeline()


def sync_forecast_pipeline():
    """執行一週預報資料更新管線"""
    try:
        raw_data = fetch_weather_data(save_to_file=True)
        parsed_data = parse_cwa_json(raw_data)
        init_database()
        save_forecast_data(parsed_data)
        return True
    except Exception as e:
        st.error(f"❌ 同步預報資料失敗: {e}")
        return False


def get_temp_color(temp: float) -> str:
    """七段式標準氣象氣溫色階"""
    if temp < 10:
        return "#2B6CB0"  # 寒冷 (<10°C)
    elif temp < 15:
        return "#3182CE"  # 涼冷 (10-15°C)
    elif temp < 20:
        return "#38A169"  # 舒適 (15-20°C)
    elif temp < 25:
        return "#ECC94B"  # 溫和 (20-25°C)
    elif temp < 30:
        return "#ED8936"  # 溫暖 (25-30°C)
    elif temp < 35:
        return "#E53E3E"  # 炎熱 (30-35°C)
    else:
        return "#9B2C2C"  # 極熱 (>35°C)


# 初始化檢查
ensure_database_loaded()

# ----------------- 側邊欄控制面板 -----------------
with st.sidebar:
    st.image("https://images.unsplash.com/photo-1592210454359-9043f067919b?w=400&auto=format&fit=crop&q=80", use_container_width=True)
    st.title("⚙️ 氣象控制面板")
    
    all_regions = get_all_regions()
    major_regions = [r for r in all_regions if "地區" in r]
    counties = [r for r in all_regions if "地區" not in r]
    ordered_regions = major_regions + counties
    default_index = ordered_regions.index("北部地區") if "北部地區" in ordered_regions else 0
    
    selected_region = st.selectbox(
        "📍 選擇預報地區：",
        options=ordered_regions,
        index=default_index,
        help="支援查詢台灣六大分區或個別縣市"
    )
    
    st.markdown("---")
    st.markdown("### 🔄 資料同步")
    if st.button("一鍵更新所有氣象資料", use_container_width=True, type="primary"):
        with st.spinner("正在連線中央氣象署抓取最新一週預報與測站資料..."):
            s1 = sync_forecast_pipeline()
            try:
                fetch_cwa_stations_data(force_refresh=True)
                s2 = True
            except Exception:
                s2 = False
                
            if s1 or s2:
                st.toast("✅ 氣象資料已成功同步更新！", icon="🎉")
                st.rerun()
                
    st.markdown("---")
    st.markdown("""
    **📚 專案資訊 (About)**
    - **課程作業**：HW10 Taiwan Weather Forecast
    - **資料來源**：
      - 一週預報：`F-D0047-091`
      - 即時測站：`O-A0001-001`
    - **技術棧**：Streamlit, SQLite, FastAPI, Leaflet, Folium
    """)

# ----------------- 主介面展示 -----------------
st.markdown('<div class="main-header">🌦️ Taiwan Weather Forecast & Observation</div>', unsafe_allow_html=True)

# 建立分頁導覽
tab1, tab2 = st.tabs(["📊 一週天氣預報 (Forecast Dashboard)", "🗺️ 全台即時氣象站地圖 (Real-time Observation Map)"])

# ----------------- Tab 1: 一週預報 -----------------
with tab1:
    st.markdown(f'<div class="sub-header">即時查詢未來一週氣溫走勢與天氣概況 • 目前選取：<strong>{selected_region}</strong></div>', unsafe_allow_html=True)
    
    df_forecast = get_forecast_by_region(selected_region)
    
    if not df_forecast.empty:
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
        
        left_col, right_col = st.columns([3, 2])
        
        with left_col:
            st.subheader(f"📊 {selected_region} — 未來一週高低溫走勢圖")
            
            chart_df = df_forecast.copy()
            chart_df = chart_df.rename(columns={"最低溫": "最低氣溫 (°C)", "最高溫": "最高氣溫 (°C)"})
            chart_df = chart_df.set_index("日期")[["最高氣溫 (°C)", "最低氣溫 (°C)"]]
            
            st.line_chart(
                chart_df,
                color=["#EF4444", "#3B82F6"],
                height=360,
                use_container_width=True
            )
            st.caption("🔴 紅線：每日預測最高溫 | 🔵 藍線：每日預測最低溫")

        with right_col:
            st.subheader("📋 逐日詳細預報數據")
            display_df = df_forecast.copy()
            display_df["平均溫 (°C)"] = ((display_df["最高溫"] + display_df["最低溫"]) / 2).round(1)
            display_df = display_df[["日期", "天氣現象", "最低溫", "最高溫", "平均溫 (°C)"]]
            display_df.rename(columns={"最低溫": "最低溫 (°C)", "最高溫": "最高溫 (°C)"}, inplace=True)
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                height=360
            )

    else:
        st.warning("⚠️ 目前資料庫中無資料，請點擊左側「一鍵更新所有氣象資料」！")

# ----------------- Tab 2: 即時氣象站地圖 -----------------
with tab2:
    st.markdown('<div class="sub-header">全台 800+ 自動氣象站即時觀測數據 • 依氣溫色階渲染標記</div>', unsafe_allow_html=True)
    
    try:
        station_data = fetch_cwa_stations_data()
        stations = station_data.get("stations", [])
    except Exception as e:
        stations = []
        st.error(f"載入測站資料失敗: {e}")
        
    if stations:
        # 統計資訊
        temps = [s["temperature_c"] for s in stations if s["temperature_c"] is not None]
        hottest_st = max(stations, key=lambda s: s["temperature_c"])
        coldest_st = min(stations, key=lambda s: s["temperature_c"])
        avg_current_temp = sum(temps) / len(temps) if temps else 0
        
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("📡 有效觀測測站數", f"{len(stations)} 站")
        with m2:
            st.metric("🌡️ 全台即時平均氣溫", f"{avg_current_temp:.1f} °C")
        with m3:
            st.metric("🔥 全台最高溫測站", f"{hottest_st['temperature_c']} °C", f"{hottest_st['station_name']} ({hottest_st['county']})")
        with m4:
            st.metric("❄️ 全台最低溫測站", f"{coldest_st['temperature_c']} °C", f"{coldest_st['station_name']} ({coldest_st['county']})", delta_color="inverse")
            
        st.markdown("---")
        
        # 測站篩選控制列
        filter_col1, filter_col2, filter_col3 = st.columns([2, 3, 2])
        
        with filter_col1:
            all_counties = sorted(list(set(s["county"] for s in stations if s.get("county"))))
            selected_county_filter = st.selectbox("🏙️ 縣市過濾：", options=["全部縣市"] + all_counties)
            
        with filter_col2:
            min_slider = int(min(temps)) if temps else 0
            max_slider = int(max(temps)) + 1 if temps else 40
            temp_range = st.slider("🌡️ 氣溫篩選區間 (°C)：", min_value=min_slider, max_value=max_slider, value=(min_slider, max_slider))
            
        with filter_col3:
            search_station = st.text_input("🔍 搜尋測站名稱：", placeholder="輸入測站名 (例: 臺北、玉山)")
            
        # 套用篩選
        filtered_stations = stations
        if selected_county_filter != "全部縣市":
            filtered_stations = [s for s in filtered_stations if s.get("county") == selected_county_filter]
        filtered_stations = [s for s in filtered_stations if temp_range[0] <= s["temperature_c"] <= temp_range[1]]
        if search_station:
            filtered_stations = [s for s in filtered_stations if search_station in s.get("station_name", "")]
            
        st.caption(f"目前顯示 **{len(filtered_stations)}** 個符合條件之測站")
        
        # 繪製地圖
        m_stations = folium.Map(location=[23.7, 120.9], zoom_start=8, tiles="OpenStreetMap")
        
        for s in filtered_stations:
            color = get_temp_color(s["temperature_c"])
            popup_html = f"""
            <div style="font-family: sans-serif; font-size: 13px; line-height: 1.5; min-width: 150px;">
                <h4 style="margin: 0 0 6px 0; color: #1E3A8A;">📍 {s['station_name']} ({s['station_id']})</h4>
                <b>所屬地區：</b> {s.get('county', '')} {s.get('town', '')}<br/>
                <b>即時氣溫：</b> <span style="color:{color};font-weight:bold;font-size:14px;">{s['temperature_c']} °C</span><br/>
                <b>相對濕度：</b> {f"{s['humidity_percent']}%" if s.get('humidity_percent') is not None else '無'}<br/>
                <b>即時風速：</b> {f"{s['wind_speed_mps']} m/s" if s.get('wind_speed_mps') is not None else '無'}<br/>
                <b>觀測時間：</b> {s.get('observed_at', '')}
            </div>
            """
            
            folium.CircleMarker(
                location=[s["lat"], s["lon"]],
                radius=6,
                color="#FFFFFF",
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.85,
                tooltip=f"{s['station_name']}: {s['temperature_c']}°C",
                popup=folium.Popup(popup_html, max_width=220)
            ).add_to(m_stations)
            
        st_folium(m_stations, width=None, height=520, returned_objects=[])
        
        # 氣溫圖例
        st.markdown("""
        <div class="legend-box">
            <span style="font-weight: 600; font-size: 0.9rem;">🎨 氣溫色階圖例：</span>
            <div class="legend-item"><div class="legend-color" style="background:#2B6CB0;"></div> &lt; 10°C 寒冷</div>
            <div class="legend-item"><div class="legend-color" style="background:#3182CE;"></div> 10 – 15°C 涼冷</div>
            <div class="legend-item"><div class="legend-color" style="background:#38A169;"></div> 15 – 20°C 舒適</div>
            <div class="legend-item"><div class="legend-color" style="background:#ECC94B;"></div> 20 – 25°C 溫和</div>
            <div class="legend-item"><div class="legend-color" style="background:#ED8936;"></div> 25 – 30°C 溫暖</div>
            <div class="legend-item"><div class="legend-color" style="background:#E53E3E;"></div> 30 – 35°C 炎熱</div>
            <div class="legend-item"><div class="legend-color" style="background:#9B2C2C;"></div> &gt; 35°C 極熱</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("尚無即時測站資料，請點擊側邊欄「一鍵更新所有氣象資料」按鈕進行抓取。")
