import streamlit as st
import plotly.express as px
import pandas as pd
import warnings
import io
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment

warnings.filterwarnings('ignore')

# ---------------------
# Page Config
# ---------------------
st.set_page_config(page_title="Telecom Network Dashboard", layout="wide")

# Fix heading overflow with CSS
st.markdown("""
    <style>
        .main-title {
            font-size: 28px !important;
            font-weight: bold;
            text-align: center;
            color: #ffffff;
            padding: 10px;
            background-color: #003366;
            border-bottom: 3px solid #0055A4;
        }
        .chart-header {
            display:flex;
            justify-content:space-between;
            align-items:center;
            font-size:20px;
            font-weight:bold;
            margin-top:25px;
            padding:8px;
            background-color:#f0f2f6;
            border-radius:6px;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Telecom Network Performance Dashboard</div>', unsafe_allow_html=True)

# ---------------------
# Load Data
# ---------------------
try:
    df_perc = pd.read_csv("sample_dataset.csv")
    df_delay = pd.read_csv("delay_dataset.csv")
except FileNotFoundError:
    st.error("CSV files not found. Make sure 'sample_dataset.csv' and 'delay_dataset.csv' exist in the project folder.")
    st.stop()

# Standardize column names
for df in [df_perc, df_delay]:
    df.columns = [c.strip().lower().replace("/", "_").replace(" ", "_") for c in df.columns]
    df["filedate"] = pd.to_datetime(df["filedate"], errors="coerce")
    df["market"] = df["market"].astype(str)

# Interval columns (original)
original_interval_cols = [c for c in df_perc.columns if c not in ["region", "market", "enodeb_gnodeb", "filedate", "risk"]]

# ---------------------
# Sidebar Filters
# ---------------------
st.sidebar.header("Filters")

combined = pd.concat(
    [df_perc[["region", "market", "enodeb_gnodeb", "filedate"]],
     df_delay[["region", "market", "enodeb_gnodeb", "filedate"]]],
    ignore_index=True
)

# Rename columns
combined.rename(columns={"enodeb_gnodeb": "gNodeB"}, inplace=True)
df_perc.rename(columns={"enodeb_gnodeb": "gNodeB"}, inplace=True)
df_delay.rename(columns={"enodeb_gnodeb": "gNodeB"}, inplace=True)

# View Mode
view_mode = st.sidebar.radio("View Mode", ["15-min Intervals", "Hourly", "Daily"])

# Resampling functions
def resample_to_hourly(df, interval_cols):
    hour_map = {f"{h:02d}": [f"{h:02d}:{m:02d}" for m in range(0, 60, 15)] for h in range(24)}
    hourly_df = df.copy()
    for hour, cols in hour_map.items():
        available = [c for c in cols if c in hourly_df.columns]
        if available:
            hourly_df[hour] = hourly_df[available].mean(axis=1)
    return hourly_df[["region", "market", "gNodeB", "filedate"] + list(hour_map.keys())]

def resample_to_daily(df, interval_cols):
    df_daily = df.copy()
    df_daily["daily_avg"] = df_daily[interval_cols].mean(axis=1)
    if "risk" in df_daily.columns:
        df_daily["risk"] = df_daily["risk"]
    else:
        df_daily["risk"] = 0
    return df_daily[["region", "market", "gNodeB", "filedate", "daily_avg", "risk"]]

# Prepare data according to view mode
if view_mode == "Hourly":
    delay_data = resample_to_hourly(df_delay, original_interval_cols)
    sample_data = resample_to_hourly(df_perc, original_interval_cols)
    interval_cols = [f"{h:02d}" for h in range(24)]

elif view_mode == "Daily":
    delay_daily = resample_to_daily(df_delay, original_interval_cols)
    sample_daily = resample_to_daily(df_perc, original_interval_cols)

    delay_daily["date"] = pd.to_datetime(delay_daily["filedate"]).dt.normalize()
    sample_daily["date"] = pd.to_datetime(sample_daily["filedate"]).dt.normalize()

    delay_daily = delay_daily.groupby(["region", "market", "gNodeB", "date"], as_index=False).agg({"daily_avg": "mean"})
    sample_daily = sample_daily.groupby(["region", "market", "gNodeB", "date"], as_index=False).agg({"daily_avg": "mean", "risk": "sum"})

    combos = combined[["region", "market", "gNodeB"]].dropna().drop_duplicates().reset_index(drop=True)
    last_date = pd.to_datetime(combined["filedate"]).max().normalize()
    last5_days = pd.date_range(end=last_date, periods=5, freq="D")

    combos["_key"] = 1
    dates_df = pd.DataFrame({"date": last5_days})
    dates_df["_key"] = 1
    grid = combos.merge(dates_df, on="_key").drop(columns=["_key"])

    sample_data = grid.merge(sample_daily, on=["region", "market", "gNodeB", "date"], how="left")
    delay_data = grid.merge(delay_daily, on=["region", "market", "gNodeB", "date"], how="left")

    interval_cols = list(last5_days)

else:
    delay_data = df_delay.copy()
    sample_data = df_perc.copy()
    interval_cols = original_interval_cols

# Problematic sites filter
risk_prone_checkbox = st.sidebar.checkbox("Show Problematic Sites Only")

if risk_prone_checkbox:
    if view_mode == "Daily":
        file_risk_sites = sample_data[sample_data["daily_avg"].fillna(100) < 100]["gNodeB"].unique()
        delay_risk_sites = delay_data[delay_data["daily_avg"].fillna(0) > 20]["gNodeB"].unique()
    else:
        file_risk_sites = sample_data[sample_data[interval_cols].min(axis=1) < 100]["gNodeB"].unique()
        delay_risk_sites = delay_data[delay_data[interval_cols].max(axis=1) > 20]["gNodeB"].unique()

    risk_gnodes = set(file_risk_sites) | set(delay_risk_sites)
    all_gnodes = sorted(list(risk_gnodes))
    if not all_gnodes:
        st.info("No problematic sites found with the current filters.")
        st.stop()
else:
    all_gnodes = sorted(combined["gNodeB"].dropna().unique().tolist())

# Region filter
all_regions = sorted(combined["region"].dropna().unique().tolist())
selected_regions = st.sidebar.multiselect("Select Region(s)", ["Select All"] + all_regions, default=["Select All"])
if "Select All" in selected_regions:
    selected_regions = all_regions

# Market filter
all_markets = sorted(combined[combined["region"].isin(selected_regions)]["market"].dropna().unique().tolist())
selected_markets = st.sidebar.multiselect("Select Market(s)", ["Select All"] + all_markets, default=["Select All"])
if "Select All" in selected_markets:
    selected_markets = all_markets

# Dates filter
all_dates = sorted(combined[(combined["region"].isin(selected_regions)) &
                             (combined["market"].isin(selected_markets))]["filedate"].dt.date.dropna().unique().tolist())
selected_dates = st.sidebar.multiselect("Select Date(s)", ["Select All"] + all_dates, default=["Select All"])
if "Select All" in selected_dates:
    selected_dates = all_dates

# gNodeB filter
selected_gnodes = st.sidebar.multiselect("Select gNodeB(s)", ["Select All"] + all_gnodes, default=["Select All"])
if "Select All" in selected_gnodes:
    selected_gnodes = all_gnodes

if view_mode == "Daily":
    selected_dates = [d.date() for d in interval_cols]
    selected_dates_dt = pd.to_datetime(selected_dates).normalize()

# Filter datasets
if view_mode == "Daily":
    delay_filtered = delay_data[(delay_data["region"].isin(selected_regions)) &
                                (delay_data["market"].isin(selected_markets)) &
                                (delay_data["date"].isin(selected_dates_dt)) &
                                (delay_data["gNodeB"].isin(selected_gnodes))]

    sample_filtered = sample_data[(sample_data["region"].isin(selected_regions)) &
                                  (sample_data["market"].isin(selected_markets)) &
                                  (sample_data["date"].isin(selected_dates_dt)) &
                                  (sample_data["gNodeB"].isin(selected_gnodes))]
else:
    delay_filtered = delay_data[(delay_data["region"].isin(selected_regions)) &
                                (delay_data["market"].isin(selected_markets)) &
                                (delay_data["filedate"].dt.date.isin(selected_dates)) &
                                (delay_data["gNodeB"].isin(selected_gnodes))]

    sample_filtered = sample_data[(sample_data["region"].isin(selected_regions)) &
                                  (sample_data["market"].isin(selected_markets)) &
                                  (sample_data["filedate"].dt.date.isin(selected_dates)) &
                                  (sample_data["gNodeB"].isin(selected_gnodes))]

total_gnodes = len(selected_gnodes)

# ---------------------
# Export to Excel Helper
# ---------------------
def df_to_excel_with_colors(df, mode="arrival"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=True, sheet_name="Data")
        workbook = writer.book
        worksheet = writer.sheets["Data"]

        for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row,
                                       min_col=2, max_col=worksheet.max_column):
            for cell in row:
                try:
                    val = float(cell.value)
                except:
                    continue
                if mode == "arrival":  # File track heatmap (blue shades)
                    if val == 100:
                        fill = PatternFill(start_color="08306b", fill_type="solid")
                        cell.font = Font(color="FFFFFF")
                    elif val >= 75:
                        fill = PatternFill(start_color="1f78ff", fill_type="solid")
                        cell.font = Font(color="FFFFFF")
                    elif val >= 50:
                        fill = PatternFill(start_color="73b3ff", fill_type="solid")
                    elif val >= 25:
                        fill = PatternFill(start_color="d0e7ff", fill_type="solid")
                    else:
                        fill = PatternFill(start_color="FF0000", fill_type="solid")
                        cell.font = Font(color="FFFFFF")
                elif mode == "delay":  # Delay heatmap (blue shades)
                    if val <= 5:
                        fill = PatternFill(start_color="d0e7ff", fill_type="solid")
                    elif val <= 10:
                        fill = PatternFill(start_color="73b3ff", fill_type="solid")
                    elif val <= 15:
                        fill = PatternFill(start_color="1f78ff", fill_type="solid")
                        cell.font = Font(color="FFFFFF")
                    else:
                        fill = PatternFill(start_color="08306b", fill_type="solid")
                        cell.font = Font(color="FFFFFF")
                cell.fill = fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
    return output.getvalue()

# ---------------------
# 1. File Arrival Track
# ---------------------
st.markdown(f'<div class="chart-header">File Arrival Track ({view_mode}) <span>Total gNodeBs: {total_gnodes}</span></div>', unsafe_allow_html=True)
if not sample_filtered.empty:
    if view_mode == "Daily":
        pivot_table = sample_filtered.pivot_table(index="gNodeB", columns="date", values="daily_avg", aggfunc="mean")
        pivot_table = pivot_table.reindex(columns=sorted(pivot_table.columns))

        def heatmap_color(val):
            if pd.isna(val):
                return ""
            if val == 100: return "background-color:#08306b; color:white"
            elif val >= 75: return "background-color:#1f78ff; color:white"
            elif val >= 50: return "background-color:#73b3ff"
            elif val >= 25: return "background-color:#d0e7ff"
            else: return "background-color:#FF0000; color:white"

        styled_table = pivot_table.style.applymap(heatmap_color).format("{:.0f}%")
        st.dataframe(styled_table, width="stretch")

        excel_bytes = df_to_excel_with_colors(pivot_table, mode="arrival")
        st.download_button("Download File Arrival Excel", data=excel_bytes, file_name="file_arrival.xlsx")
    else:
        pivot_table = sample_filtered.pivot_table(index="gNodeB", values=interval_cols, aggfunc="mean")

        def heatmap_color(val):
            if val == 100: return "background-color:#08306b; color:white"
            elif val >= 75: return "background-color:#1f78ff; color:white"
            elif val >= 50: return "background-color:#73b3ff"
            elif val >= 25: return "background-color:#d0e7ff"
            else: return "background-color:#FF0000; color:white"

        styled_table = pivot_table.style.applymap(heatmap_color).format("{:.0f}%")
        st.dataframe(styled_table, width="stretch")

        excel_bytes = df_to_excel_with_colors(pivot_table, mode="arrival")
        st.download_button("Download File Arrival Excel", data=excel_bytes, file_name="file_arrival.xlsx")
    
    st.markdown("""
        **Legend:** <div style="display:flex;gap:15px;">
            <div style="background-color:#08306b;width:20px;height:20px;border:1px solid #000"></div> 100% (Perfect)
            <div style="background-color:#1f78ff;width:20px;height:20px;border:1px solid #000"></div> ≥75%
            <div style="background-color:#73b3ff;width:20px;height:20px;border:1px solid #000"></div> ≥50%
            <div style="background-color:#d0e7ff;width:20px;height:20px;border:1px solid #000"></div> ≥25%
            <div style="background-color:#FF0000;width:20px;height:20px;border:1px solid #000"></div> <25%
        </div>
    """, unsafe_allow_html=True)

# ---------------------
# 2. Delay Heatmap
# ---------------------
st.markdown(f'<div class="chart-header">Delay Heatmap ({view_mode}) <span>Total gNodeBs: {total_gnodes}</span></div>', unsafe_allow_html=True)
if not delay_filtered.empty:
    if view_mode == "Daily":
        pivot_delay = delay_filtered.pivot_table(index="gNodeB", columns="date", values="daily_avg", aggfunc="mean")
        pivot_delay = pivot_delay.reindex(columns=sorted(pivot_delay.columns))

        def delay_color(val):
            if pd.isna(val):
                return ""
            if val <= 5: return "background-color:#d0e7ff"
            elif val <= 10: return "background-color:#73b3ff"
            elif val <= 15: return "background-color:#1f78ff; color:white"
            else: return "background-color:#08306b; color:white"

        styled_delay = pivot_delay.style.applymap(delay_color).format("{:.1f} min")
        st.dataframe(styled_delay, width="stretch")

        excel_bytes = df_to_excel_with_colors(pivot_delay, mode="delay")
        st.download_button("Download Delay Heatmap Excel", data=excel_bytes, file_name="delay_heatmap.xlsx")
    else:
        pivot_delay = delay_filtered.pivot_table(index="gNodeB", values=interval_cols, aggfunc="mean")

        def delay_color(val):
            if val <= 5: return "background-color:#d0e7ff"
            elif val <= 10: return "background-color:#73b3ff"
            elif val <= 15: return "background-color:#1f78ff; color:white"
            else: return "background-color:#08306b; color:white"

        styled_delay = pivot_delay.style.applymap(delay_color).format("{:.1f} min")
        st.dataframe(styled_delay, width="stretch")

        excel_bytes = df_to_excel_with_colors(pivot_delay, mode="delay")
        st.download_button("Download Delay Heatmap Excel", data=excel_bytes, file_name="delay_heatmap.xlsx")
    st.markdown("""
        **Legend (minutes):** <div style="display:flex;gap:15px;">
            <div style="background-color:#d0e7ff;width:20px;height:20px;border:1px solid #000"></div> 0–5 min
            <div style="background-color:#73b3ff;width:20px;height:20px;border:1px solid #000"></div> 5–10 min
            <div style="background-color:#1f78ff;width:20px;height:20px;border:1px solid #000"></div> 10–15 min
            <div style="background-color:#08306b;width:20px;height:20px;border:1px solid #000"></div> 15+ min
        </div>
    """, unsafe_allow_html=True)


# ---------------------
# 3. Latency Trend
# ---------------------
st.markdown(f'<div class="chart-header">📊 Latency Trend by gNodeB ({view_mode}) <span>Total gNodeBs: {total_gnodes}</span></div>', unsafe_allow_html=True)
if view_mode == "Daily":
    if not delay_filtered.empty:
        gnodeb_choice = st.selectbox("Select gNodeB for Latency Trend", options=selected_gnodes, index=0)
        melted_delay = delay_filtered[delay_filtered["gNodeB"] == gnodeb_choice][["date", "daily_avg"]].copy()
        if not melted_delay.empty:
            melted_delay["date_str"] = melted_delay["date"].dt.strftime('%Y-%m-%d')
            melted_delay = melted_delay.sort_values("date")
            fig_delay = px.bar(melted_delay, x="date_str", y="daily_avg", title=f"Latency Trend - gNodeB: {gnodeb_choice}")
            fig_delay.add_hline(y=10, line_dash="dash", line_color="red", annotation_text="Threshold = 10 min")
            fig_delay.update_xaxes(categoryorder="category ascending")
            st.plotly_chart(fig_delay, use_container_width=True)
else:
    if not delay_filtered.empty:
        gnodeb_choice = st.selectbox("Select gNodeB for Latency Trend", options=selected_gnodes, index=0)
        melted_delay = delay_filtered[delay_filtered["gNodeB"] == gnodeb_choice].melt(
            id_vars=["gNodeB"],
            value_vars=interval_cols,
            var_name="interval",
            value_name="delay"
        )
        fig_delay = px.bar(melted_delay, x="interval", y="delay", color="gNodeB",
                           barmode="group", title=f"Latency Trend - gNodeB: {gnodeb_choice}")
        fig_delay.add_hline(y=10, line_dash="dash", line_color="red", annotation_text="Threshold = 10 min")
        fig_delay.update_xaxes(categoryorder="category ascending")
        st.plotly_chart(fig_delay, use_container_width=True)

# ---------------------
# 4. Average Delay
# ---------------------
st.markdown(f'<div class="chart-header">📍 Average Delay by Region & Market ({view_mode}) <span>Total gNodeBs: {total_gnodes}</span></div>', unsafe_allow_html=True)
if view_mode == "Daily":
    if not delay_filtered.empty:
        col3, col4 = st.columns(2)
        delay_avg_region = delay_filtered.groupby("region")["daily_avg"].mean().reset_index(name="avg_delay")
        fig3 = px.bar(delay_avg_region, x="region", y="avg_delay", title="Average Delay by Region", text_auto=True)
        fig3.update_xaxes(categoryorder="category ascending")
        col3.plotly_chart(fig3, use_container_width=True)

        delay_avg_market = delay_filtered.groupby("market")["daily_avg"].mean().reset_index(name="avg_delay")
        fig4 = px.bar(delay_avg_market, x="market", y="avg_delay", title="Average Delay by Market", text_auto=True)
        fig4.update_xaxes(type="category", categoryorder="category ascending")
        col4.plotly_chart(fig4, use_container_width=True)
else:
    if not delay_filtered.empty:
        col3, col4 = st.columns(2)
        delay_avg_region = delay_filtered.groupby("region")[interval_cols].mean().mean(axis=1).reset_index(name="avg_delay")
        fig3 = px.bar(delay_avg_region, x="region", y="avg_delay", title="Average Delay by Region", text_auto=True)
        fig3.update_xaxes(categoryorder="category ascending")
        col3.plotly_chart(fig3, use_container_width=True)

        delay_avg_market = delay_filtered.groupby("market")[interval_cols].mean().mean(axis=1).reset_index(name="avg_delay")
        fig4 = px.bar(delay_avg_market, x="market", y="avg_delay", title="Average Delay by Market", text_auto=True)
        fig4.update_xaxes(type="category", categoryorder="category ascending")
        col4.plotly_chart(fig4, use_container_width=True)

# ---------------------
# 5. Problematic Sites Count
# ---------------------
st.markdown(f'<div class="chart-header">⚠️ Problematic Sites Count ({view_mode}) <span>Total gNodeBs: {total_gnodes}</span></div>', unsafe_allow_html=True)
if view_mode == "Daily":
    if not sample_filtered.empty and "risk" in sample_filtered.columns:
        col5, col6 = st.columns(2)
        risk_region = sample_filtered.groupby("region")["risk"].sum().reset_index()
        fig5 = px.bar(risk_region, x="region", y="risk", title="Problematic Sites by Region", text_auto=True)
        fig5.update_xaxes(categoryorder="category ascending")
        col5.plotly_chart(fig5, use_container_width=True)

        risk_market = sample_filtered.groupby("market")["risk"].sum().reset_index()
        fig6 = px.bar(risk_market, x="market", y="risk", title="Problematic Sites by Market", text_auto=True)
        fig6.update_xaxes(type="category", categoryorder="category ascending")
        col6.plotly_chart(fig6, use_container_width=True)
else:
    if not sample_filtered.empty and "risk" in sample_filtered.columns:
        col5, col6 = st.columns(2)
        risk_region = sample_filtered.groupby("region")["risk"].sum().reset_index()
        fig5 = px.bar(risk_region, x="region", y="risk", title="Problematic Sites by Region", text_auto=True)
        col5.plotly_chart(fig5, use_container_width=True)

        risk_market = sample_filtered.groupby("market")["risk"].sum().reset_index()
        fig6 = px.bar(risk_market, x="market", y="risk", title="Problematic Sites by Market", text_auto=True)
        fig6.update_xaxes(type="category")
        col6.plotly_chart(fig6, use_container_width=True)

# ---------------------
# 6. Market Pie
# ---------------------
st.markdown(f'<div class="chart-header">🥧 Zero-Interval Distribution by Market ({view_mode}) <span>Total gNodeBs: {total_gnodes}</span></div>', unsafe_allow_html=True)
if view_mode != "Daily":
    if not sample_filtered.empty:
        melted_percent = sample_filtered.melt(
            id_vars=["market"], value_vars=interval_cols,
            var_name="interval", value_name="value"
        )
        melted_percent["zero_flag"] = melted_percent["value"].apply(lambda x: 1 if x == 0 else 0)
        pie_df = melted_percent.groupby("market")["zero_flag"].sum().reset_index()
        fig7 = px.pie(pie_df, values="zero_flag", names="market", title="Zero-Interval Counts by Market")
        st.plotly_chart(fig7, use_container_width=True)
else:
    # For Daily view: count zero daily_avg values across the 5-day window
    if not sample_filtered.empty:
        sample_filtered["zero_flag"] = sample_filtered["daily_avg"].apply(lambda x: 1 if pd.notna(x) and x == 0 else 0)
        pie_df = sample_filtered.groupby("market")["zero_flag"].sum().reset_index()
        fig7 = px.pie(pie_df, values="zero_flag", names="market", title="Zero-Interval Counts by Market (last 5 days)")
        st.plotly_chart(fig7, use_container_width=True)

    else:
        st.info("Zero-interval pie not applicable for Daily view.")
