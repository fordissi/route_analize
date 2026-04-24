import sys
from pathlib import Path

def build_demo_app():
    root_dir = Path(__file__).resolve().parent.parent
    app_path = root_dir / "app.py"
    demo_app_path = root_dir / "demo_app.py"
    
    lines = app_path.read_text(encoding="utf-8").splitlines()
    
    # Identify key indices
    load_results_def_idx = -1
    tabs_def_idx = -1
    tab_daily_idx = -1
    tab_period_idx = -1
    tab_overview_idx = -1
    
    for i, line in enumerate(lines):
        if line.startswith("def load_results()"):
            load_results_def_idx = i
        if "= st.tabs(" in line and "tab_home" in line:
            tabs_def_idx = i
        if line.startswith("with tab_daily:"):
            tab_daily_idx = i
        if line.startswith("with tab_period:"):
            tab_period_idx = i
        if line.startswith("with tab_overview:"):
            tab_overview_idx = i
            
    header_lines = lines[:load_results_def_idx+1]
    
    # Modify load_results
    header_lines.append("    config = build_config(root_dir=Path(__file__).resolve().parent / 'demo_data')")
    
    # We skip run_pipeline in demo
    mid_lines = lines[load_results_def_idx+3 : tabs_def_idx]
    
    new_tabs = 'tab_demo, tab_daily, tab_period = st.tabs(["🎉 專案展示 (Demo Home)", "📍 單日出勤軌跡 (Daily Map)", "📊 月報異常稽核 (Audit Report)"])'
    
    demo_tab_content = """
with tab_demo:
    st.markdown(
        \"\"\"
        <div style='background: rgba(255, 255, 255, 0.4); backdrop-filter: blur(10px); padding: 4rem 2rem; border-radius: 20px; text-align: center; border: 1px solid rgba(255,255,255,0.6); margin-bottom: 2rem; margin-top: 1rem;'>
            <h1 style='font-size: 3.5rem; font-weight: 900; color: #0f172a; margin-bottom: 1rem;'>Data-Driven Field Sales Audit</h1>
            <p style='font-size: 1.3rem; color: #334155;'>完全無縫整合企業 104 HR 行動打卡紀錄，透過 Google Routes API 軌跡還原技術，<br>自動化排查異常出勤、預估真實公務里程，杜絕浮報油資，打造公平透明的業務績效環境。</p>
        </div>
        \"\"\",
        unsafe_allow_html=True
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(\"\"\"
    <div style='background: rgba(255,255,255,0.8); padding: 2rem; border-radius: 16px; height: 100%; border: 1px solid rgba(0,0,0,0.05); box-shadow: 0 4px 15px rgba(0,0,0,0.03);'>
        <h3 style='font-size: 1.4rem; color: #1d4ed8; margin-bottom: 1rem;'>🎯 科學化軌跡還原</h3>
        <p style='color: #475569; line-height: 1.6;'>打破過去「只看單點距離」的盲點，系統根據打卡時間序重組行車路徑，串接 Google Routes API 計算最真實的行車距離與移動時間，讓好員工不委屈，異常行為無所遁形。</p>
    </div>
    \"\"\", unsafe_allow_html=True)
    
    col2.markdown(\"\"\"
    <div style='background: rgba(255,255,255,0.8); padding: 2rem; border-radius: 16px; height: 100%; border: 1px solid rgba(0,0,0,0.05); box-shadow: 0 4px 15px rgba(0,0,0,0.03);'>
        <h3 style='font-size: 1.4rem; color: #16a34a; margin-bottom: 1rem;'>🚦 自動化異常稽核</h3>
        <p style='color: #475569; line-height: 1.6;'>透過自訂寬容值(例如15%、30%)，系統自動將業務的油資申報與「系統推估值」進行比對，標記出「綠燈(合格)、黃燈(注意)、紅燈(異常)」，讓財務審核時間從數天縮短為數分鐘。</p>
    </div>
    \"\"\", unsafe_allow_html=True)
    
    col3.markdown(\"\"\"
    <div style='background: rgba(255,255,255,0.8); padding: 2rem; border-radius: 16px; height: 100%; border: 1px solid rgba(0,0,0,0.05); box-shadow: 0 4px 15px rgba(0,0,0,0.03);'>
        <h3 style='font-size: 1.4rem; color: #e11d48; margin-bottom: 1rem;'>🔒 無痛零信任導入</h3>
        <p style='color: #475569; line-height: 1.6;'>系統完全不侵犯設備隱私，業務無須安裝任何監控 App 或更改現有操作流程。所有分析均基於既有的人資打卡 GPS 資料運行，實現真正的無痕管理與零信任架構落地。</p>
    </div>
    \"\"\", unsafe_allow_html=True)
    
    st.markdown(\"\"\"
    <div style='margin-top: 3rem; background: #f8fafc; padding: 2rem; border-radius: 12px; border-left: 6px solid #475569;'>
        <h4 style='margin: 0 0 1rem 0; color: #334155;'>💡 Demo 情境導覽建議</h4>
        <ul style='color: #475569; line-height: 1.8; margin: 0;'>
            <li><b>單日出勤軌跡</b>: 切換至 [📍 單日出勤軌跡] 頁籤，選擇模範員工「張守規」查看完美還原的拜訪路徑；再切換至問題員工「李繞路」，觀察系統如何精準抓出繞路吃臭豆腐、在家打卡等異常點。</li>
            <li><b>月報異常稽核</b>: 切換至 [📊 月報異常稽核] 頁籤，查看月度總表。系統會直接把李繞路浮報 85km 的誇張行為標為紅燈，供財會查核。</li>
        </ul>
    </div>
    \"\"\", unsafe_allow_html=True)
"""
    
    daily_tab_content = "\n".join(lines[tab_daily_idx:tab_period_idx])
    period_tab_content = "\n".join(lines[tab_period_idx:tab_overview_idx])
    
    final_content = "\n".join(header_lines) + "\n" + "\n".join(mid_lines) + "\n\n" + new_tabs + "\n" + demo_tab_content + "\n" + daily_tab_content + "\n" + period_tab_content
    
    demo_app_path.write_text(final_content, encoding="utf-8")
    print("Successfully built demo_app.py!")

if __name__ == "__main__":
    build_demo_app()
