import streamlit as st
import plotly.express as px
import pandas as pd
import warnings

warnings.filterwarnings('ignore')

# ---------------------
# Page Config
# ---------------------
st.set_page_config(page_title="Network Dashboard", page_icon=":bar_chart:", layout="wide")
st.title("📊 Network Delay & Percentage Dashboard")
st.markdown('<style>div.block-container{padding-top:1rem;}</style>', unsafe_allow_html=True)

# ---------------------
# Load Data
# ---------------------
try:
    df_perc = pd.read_csv("sample_dataset.csv")
    df_delay = pd.read_csv("delay_dataset.csv")
except FileNotFoundError:
    st.error("❌ CSV files not found. Make sure 'sample_dataset.csv' and 'delay_dataset.csv' exist in the project folder.")
    st.stop()

# Standardize column names
for df in [df_perc, df_delay]:
    df.columns = [c.strip().lower().replace("/", "_").replace(" ", "_") for c in df.columns]
    df["filedate"] = pd.to_datetime(df["filedate"], errors="coerce")

    

# Interval columns (take from whichever dataset has them)
interval_cols = [c for c in df_perc.columns if c not in ["region", "market", "enodeb_gnodeb", "filedate", "risk"]]

# ---------------------
# Sidebar Filters (from UNION of both datasets)
# ---------------------
st.sidebar.header("Filters")

combined = pd.concat([df_perc[["region","market","enodeb_gnodeb","filedate"]],
                      df_delay[["region","market","enodeb_gnodeb","filedate"]]], ignore_index=True)

# Region
all_regions = sorted(combined["region"].dropna().unique().tolist())
selected_regions = st.sidebar.multiselect("Select Region(s)", ["Select All"] + all_regions, default=["Select All"])
if "Select All" in selected_regions:
    selected_regions = all_regions

# Market
all_markets = sorted(combined[combined["region"].isin(selected_regions)]["market"].dropna().unique().tolist())
selected_markets = st.sidebar.multiselect("Select Market(s)", ["Select All"] + all_markets, default=["Select All"])
if "Select All" in selected_markets:
    selected_markets = all_markets

# Dates
all_dates = sorted(combined[(combined["region"].isin(selected_regions)) &
                            (combined["market"].isin(selected_markets))]["filedate"].dt.date.dropna().unique().tolist())
selected_dates = st.sidebar.multiselect("Select Date(s)", ["Select All"] + all_dates, default=["Select All"])
if "Select All" in selected_dates:
    selected_dates = all_dates

# Enode/GnodeB
all_enodes = sorted(combined[(combined["region"].isin(selected_regions)) &
                             (combined["market"].isin(selected_markets)) &
                             (combined["filedate"].dt.date.isin(selected_dates))]["enodeb_gnodeb"].dropna().unique().tolist())
selected_enodes = st.sidebar.multiselect("Select Enode/GNodeB(s)", ["Select All"] + all_enodes, default=["Select All"])
if "Select All" in selected_enodes:
    selected_enodes = all_enodes

# ---------------------
# Apply filters independently to both datasets
# ---------------------
delay_filtered = df_delay[(df_delay["region"].isin(selected_regions)) &
                          (df_delay["market"].isin(selected_markets)) &
                          (df_delay["filedate"].dt.date.isin(selected_dates)) &
                          (df_delay["enodeb_gnodeb"].isin(selected_enodes))]

sample_filtered = df_perc[(df_perc["region"].isin(selected_regions)) &
                          (df_perc["market"].isin(selected_markets)) &
                          (df_perc["filedate"].dt.date.isin(selected_dates)) &
                          (df_perc["enodeb_gnodeb"].isin(selected_enodes))]

# ---------------------
# Delay Chart
# ---------------------
st.subheader("⏱️ Delay Data (per enodeb_gnodeb)")
if not delay_filtered.empty:
    melted_delay = delay_filtered.melt(
        id_vars=["enodeb_gnodeb"],
        value_vars=interval_cols,
        var_name="interval",
        value_name="delay"
    )
    fig_delay = px.bar(melted_delay, x="interval", y="delay", color="enodeb_gnodeb",
                       barmode="group", title="Delay per Interval by enodeb_gnodeb")
    fig_delay.add_hline(y=10, line_dash="dash", line_color="red", annotation_text="Threshold = 10")
    st.plotly_chart(fig_delay, use_container_width=True)
else:
    st.info("No Delay data available for selected filters.")

# ---------------------
# Percentage Table
# ---------------------
st.subheader("📊 Percentage Data (Enodeb × Intervals)")
if not sample_filtered.empty:
    pivot_table = sample_filtered.pivot_table(index="enodeb_gnodeb", values=interval_cols, aggfunc="mean")
    styled_table = pivot_table.style.applymap(
        lambda v: "background-color: green; color: white" if v == 100 else
                  ("background-color: red; color: white" if v == 0 else "")
    )
    st.write(styled_table)
else:
    st.info("No Percentage data available for selected filters.")

# ---------------------
# Average Delay
# ---------------------
st.subheader("📍 Average Delay by Region and Market")
if not delay_filtered.empty:
    col3, col4 = st.columns(2)
    delay_avg_region = delay_filtered.groupby("region")[interval_cols].mean().mean(axis=1).reset_index(name="avg_delay")
    fig3 = px.bar(delay_avg_region, x="region", y="avg_delay", title="Average Delay by Region", text_auto=True)
    col3.plotly_chart(fig3, use_container_width=True)

    delay_avg_market = delay_filtered.groupby("market")[interval_cols].mean().mean(axis=1).reset_index(name="avg_delay")
    delay_avg_market["market"] = delay_avg_market["market"].astype(str)
    fig4 = px.bar(delay_avg_market.astype(str), x="market", y="avg_delay", title="Average Delay by Market", text_auto=True)
    fig4.update_xaxes(type="category")  # ensure categorical axis

    col4.plotly_chart(fig4, use_container_width=True)
else:
    st.info("No Delay averages available for selected filters.")

# ---------------------
# Risk Count
# ---------------------
st.subheader("⚠️ Risk Count by Region and Market")
if not sample_filtered.empty and "risk" in sample_filtered.columns:
    col5, col6 = st.columns(2)
    risk_region = sample_filtered.groupby("region")["risk"].sum().reset_index()
    fig5 = px.bar(risk_region, x="region", y="risk", title="Risk Count by Region", text_auto=True)
    col5.plotly_chart(fig5, use_container_width=True)

    risk_market = sample_filtered.groupby("market")["risk"].sum().reset_index()
    risk_market["market"] = risk_market["market"].astype(str)
    fig6 = px.bar(risk_market, x="market", y="risk", title="Risk Count by Market", text_auto=True)
    fig6.update_xaxes(type="category")  

    col6.plotly_chart(fig6, use_container_width=True)
else:
    st.info("No Risk data available for selected filters.")

# ---------------------
# Market Pie
# ---------------------
st.subheader("🥧 Market-wise Zero Intervals")
if not sample_filtered.empty:
    melted_percent = sample_filtered.melt(
        id_vars=["market"], value_vars=interval_cols,
        var_name="interval", value_name="value"
    )
    melted_percent["zero_flag"] = melted_percent["value"].apply(lambda x: 1 if x == 0 else 0)
    pie_df = melted_percent.groupby("market")["zero_flag"].sum().reset_index()
    fig7 = px.pie(pie_df, values="zero_flag", names="market", title="Intervals with Zero per Market")
    st.plotly_chart(fig7, use_container_width=True)
else:
    st.info("No Zero-interval data available for selected filters.")
