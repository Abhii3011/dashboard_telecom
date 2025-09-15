import streamlit as st
import plotly.express as px
import pandas as pd
import warnings

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

# Resampling
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
    return df_daily[["region", "market", "gNodeB", "filedate", "daily_avg"]]

if view_mode == "Hourly":
    delay_data = resample_to_hourly(df_delay, original_interval_cols)
    sample_data = resample_to_hourly(df_perc, original_interval_cols)
    interval_cols = [f"{h:02d}" for h in range(24)]
elif view_mode == "Daily":
    delay_data = resample_to_daily(df_delay, original_interval_cols)
    sample_data = resample_to_daily(df_perc, original_interval_cols)
    interval_cols = ["daily_avg"]
else:
    delay_data = df_delay.copy()
    sample_data = df_perc.copy()
    interval_cols = original_interval_cols

# Risk-prone sites filter
risk_prone_checkbox = st.sidebar.checkbox("Show Risk-Prone Sites Only")

# Determine Risk-Prone Sites
if risk_prone_checkbox:
    # Check for file arrival below 100%
    file_risk_sites = sample_data[sample_data[interval_cols].min(axis=1) < 100]["gNodeB"].unique()
    
    # Check for delay > 20 minutes (1200 seconds)
    delay_risk_sites = delay_data[delay_data[interval_cols].max(axis=1) > 20 * 60]["gNodeB"].unique()
    
    # Combine and get unique risk sites
    risk_gnodes = set(file_risk_sites) | set(delay_risk_sites)
    all_gnodes = sorted(list(risk_gnodes))
    
    if not all_gnodes:
        st.info("No risk-prone sites found with the current filters.")
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

# Filter datasets
delay_filtered = delay_data[(delay_data["region"].isin(selected_regions)) &
                            (delay_data["market"].isin(selected_markets)) &
                            (delay_data["filedate"].dt.date.isin(selected_dates)) &
                            (delay_data["gNodeB"].isin(selected_gnodes))]

sample_filtered = sample_data[(sample_data["region"].isin(selected_regions)) &
                              (sample_data["market"].isin(selected_markets)) &
                              (sample_data["filedate"].dt.date.isin(selected_dates)) &
                              (sample_data["gNodeB"].isin(selected_gnodes))]

# ---------------------
# gNodeB Count
# ---------------------
st.markdown(f"Total gNodeBs: **{len(selected_gnodes)}**")

# ---------------------
# 1. File Arrival Track
# ---------------------
st.subheader(f"File Arrival Track ({view_mode})")
if not sample_filtered.empty:
    pivot_table = sample_filtered.pivot_table(index="gNodeB", values=interval_cols, aggfunc="mean")

    def perc_color(val):
        return "background-color: #2E8B57; color: white" if val == 100 else "background-color: #B22222; color: white"

    styled_table = pivot_table.style.applymap(perc_color).format("{:.0f}%")
    st.dataframe(styled_table, width="stretch")
    
    st.markdown("""
        **Legend:** <div style="display:flex;gap:15px;">
            <div style="background-color:#2E8B57;width:20px;height:20px;border:1px solid #000"></div> 100% (File Arrived)
            <div style="background-color:#B22222;width:20px;height:20px;border:1px solid #000"></div> < 100% (File Missing)
        </div>
    """, unsafe_allow_html=True)

else:
    st.info("No File Arrival data available.")

# ---------------------
# 2. Delay Heatmap
# ---------------------
st.subheader(f"Delay Heatmap ({view_mode})")
if not delay_filtered.empty:
    pivot_delay = delay_filtered.pivot_table(index="gNodeB", values=interval_cols, aggfunc="mean")

    def delay_color(val):
        if val <= 5: return "background-color: #d0e7ff"
        elif val <= 10: return "background-color: #73b3ff"
        elif val <= 15: return "background-color: #1f78ff; color: white"
        else: return "background-color: #08306b; color: white"

    styled_delay = pivot_delay.style.applymap(delay_color).format("{:.2f}")
    st.dataframe(styled_delay, width="stretch")

    st.markdown("""
        **Legend:** <div style="display:flex;gap:15px;">
            <div style="background-color:#d0e7ff;width:20px;height:20px;border:1px solid #000"></div> 0–5 ms 
            <div style="background-color:#73b3ff;width:20px;height:20px;border:1px solid #000"></div> 5–10 ms 
            <div style="background-color:#1f78ff;width:20px;height:20px;border:1px solid #000"></div> 10–15 ms 
            <div style="background-color:#08306b;width:20px;height:20px;border:1px solid #000"></div> 15+ ms 
        </div>
    """, unsafe_allow_html=True)
else:
    st.info("No Delay heatmap data available.")

# ---------------------
# 3. Latency Trend
# ---------------------
st.subheader(f"Latency Trend by gNodeB ({view_mode})")
if not delay_filtered.empty:
    melted_delay = delay_filtered.melt(
        id_vars=["gNodeB"],
        value_vars=interval_cols,
        var_name="interval",
        value_name="delay"
    )
    fig_delay = px.bar(melted_delay, x="interval", y="delay", color="gNodeB",
                       barmode="group", title=f"Latency per {view_mode} by gNodeB")
    fig_delay.add_hline(y=10, line_dash="dash", line_color="red", annotation_text="Threshold = 10")
    st.plotly_chart(fig_delay, width="stretch")
else:
    st.info("No Delay data available.")

# ---------------------
# 4. Average Delay
# ---------------------
st.subheader(f"Average Delay by Region and Market ({view_mode})")
if not delay_filtered.empty:
    col3, col4 = st.columns(2)
    delay_avg_region = delay_filtered.groupby("region")[interval_cols].mean().mean(axis=1).reset_index(name="avg_delay")
    fig3 = px.bar(delay_avg_region, x="region", y="avg_delay", title="Average Delay by Region", text_auto=True)
    col3.plotly_chart(fig3, width="stretch")

    delay_avg_market = delay_filtered.groupby("market")[interval_cols].mean().mean(axis=1).reset_index(name="avg_delay")
    fig4 = px.bar(delay_avg_market, x="market", y="avg_delay", title="Average Delay by Market", text_auto=True)
    fig4.update_xaxes(type="category")
    col4.plotly_chart(fig4, width="stretch")
else:
    st.info("No Delay averages available.")

# ---------------------
# 5. Risk Count
# ---------------------
st.subheader(f"Risk Count by Region and Market ({view_mode})")
if not sample_filtered.empty and "risk" in sample_filtered.columns:
    col5, col6 = st.columns(2)
    risk_region = sample_filtered.groupby("region")["risk"].sum().reset_index()
    fig5 = px.bar(risk_region, x="region", y="risk", title="Risk Count by Region", text_auto=True)
    col5.plotly_chart(fig5, width="stretch")

    risk_market = sample_filtered.groupby("market")["risk"].sum().reset_index()
    fig6 = px.bar(risk_market, x="market", y="risk", title="Risk Count by Market", text_auto=True)
    fig6.update_xaxes(type="category")
    col6.plotly_chart(fig6, width="stretch")
else:
    st.info("No Risk data available.")

# ---------------------
# 6. Market Pie
# ---------------------
st.subheader(f"Zero-Interval Distribution by Market ({view_mode})")
if not sample_filtered.empty and view_mode != "Daily":
    melted_percent = sample_filtered.melt(
        id_vars=["market"], value_vars=interval_cols,
        var_name="interval", value_name="value"
    )
    melted_percent["zero_flag"] = melted_percent["value"].apply(lambda x: 1 if x == 0 else 0)
    pie_df = melted_percent.groupby("market")["zero_flag"].sum().reset_index()
    fig7 = px.pie(pie_df, values="zero_flag", names="market", title="Zero-Interval Counts by Market")
    st.plotly_chart(fig7, width="stretch")
elif view_mode == "Daily":
    st.info("Zero-interval pie not applicable for Daily view.")
else:
    st.info("No Zero-interval data available.")