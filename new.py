import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff
import numpy as np

# ==============================
# Load Data
# ==============================
@st.cache_data
def load_data():
    df_perc = pd.read_csv("sample_dataset.csv")
    df_delay = pd.read_csv("delay_dataset.csv")

    # Ensure filedate is datetime
    df_perc["filedate"] = pd.to_datetime(df_perc["filedate"])
    df_delay["filedate"] = pd.to_datetime(df_delay["filedate"])

    return df_perc, df_delay

df_perc, df_delay = load_data()

# ==============================
# Sidebar Filters
# ==============================
st.sidebar.header("Filters")

# Cascading filters
regions = df_delay["region"].unique()
selected_region = st.sidebar.selectbox("Select Region", options=regions)

markets = df_delay[df_delay["region"] == selected_region]["market"].unique()
selected_market = st.sidebar.selectbox("Select Market", options=markets)

dates = df_delay[(df_delay["region"] == selected_region) &
                 (df_delay["market"] == selected_market)]["filedate"].dt.date.unique()
selected_date = st.sidebar.selectbox("Select Date", options=sorted(dates))

enodes = df_delay[(df_delay["region"] == selected_region) &
                  (df_delay["market"] == selected_market) &
                  (df_delay["filedate"].dt.date == selected_date)]["enodeb_gnodeb"].unique()
selected_enode = st.sidebar.selectbox("Select Enode/GNodeB", options=enodes)

# Final filter dataset
filtered_delay = df_delay[(df_delay["region"] == selected_region) &
                          (df_delay["market"] == selected_market) &
                          (df_delay["filedate"].dt.date == selected_date) &
                          (df_delay["enodeb_gnodeb"] == selected_enode)]

filtered_perc = df_perc[(df_perc["region"] == selected_region) &
                        (df_perc["market"] == selected_market) &
                        (df_perc["filedate"].dt.date == selected_date) &
                        (df_perc["enodeb_gnodeb"] == selected_enode)]

# ==============================
# Delay Bar Chart with Threshold
# ==============================
st.subheader("📊 Delay by Interval")

interval_cols = [col for col in filtered_delay.columns if ":" in col]
df_long = filtered_delay.melt(id_vars=["region","market","filedate","enodeb_gnodeb"],
                              value_vars=interval_cols,
                              var_name="Interval", value_name="Delay")

fig_delay = px.bar(df_long, x="Interval", y="Delay", color="enodeb_gnodeb",
                   barmode="group", title="Delay per Interval")
fig_delay.add_hline(y=10, line_color="red", line_dash="dash", annotation_text="Threshold=10")
st.plotly_chart(fig_delay, use_container_width=True)

# ==============================
# Percentage Table (Heatmap Style)
# ==============================
st.subheader("📊 Percentage Table by Enode/GNodeB and Interval")

if not filtered_perc.empty:
    interval_cols_perc = [col for col in filtered_perc.columns if ":" in col]
    df_pivot = filtered_perc.melt(id_vars=["enodeb_gnodeb"], value_vars=interval_cols_perc,
                                  var_name="Interval", value_name="Percentage")
    df_table = df_pivot.pivot(index="enodeb_gnodeb", columns="Interval", values="Percentage")

    def color_cells(val):
        if val == 100:
            return "background-color: green; color: white"
        elif val == 0:
            return "background-color: red; color: white"
        return ""

    st.dataframe(df_table.style.applymap(color_cells))

# ==============================
# Average Delay by Market & Region
# ==============================
st.subheader("📊 Average Delay by Market")
avg_market = df_delay.groupby("market")[interval_cols].mean().mean(axis=1).reset_index(name="Avg Delay")
fig_market = px.bar(avg_market, x="market", y="Avg Delay", title="Average Delay by Market")
st.plotly_chart(fig_market, use_container_width=True)

st.subheader("📊 Average Delay by Region")
avg_region = df_delay.groupby("region")[interval_cols].mean().mean(axis=1).reset_index(name="Avg Delay")
fig_region = px.bar(avg_region, x="region", y="Avg Delay", title="Average Delay by Region")
st.plotly_chart(fig_region, use_container_width=True)

# ==============================
# Risk Count by Region & Market
# ==============================
st.subheader("📊 Risk Count by Region")
risk_region = df_perc.groupby("region")["risk"].sum().reset_index()
fig_risk_region = px.bar(risk_region, x="region", y="risk", title="Risk Count by Region")
st.plotly_chart(fig_risk_region, use_container_width=True)

st.subheader("📊 Risk Count by Market")
risk_market = df_perc.groupby("market")["risk"].sum().reset_index()
fig_risk_market = px.bar(risk_market, x="market", y="risk", title="Risk Count by Market")
st.plotly_chart(fig_risk_market, use_container_width=True)

# ==============================
# Date Range Filter
# ==============================
st.sidebar.subheader("📅 Date Range Filter")
startDate = pd.to_datetime(df_perc["filedate"]).min()
endDate = pd.to_datetime(df_perc["filedate"]).max()

col1, col2 = st.sidebar.columns(2)
date1 = pd.to_datetime(st.sidebar.date_input("Start Date", startDate))
date2 = pd.to_datetime(st.sidebar.date_input("End Date", endDate))

df_perc_range = df_perc[(df_perc["filedate"] >= date1) & (df_perc["filedate"] <= date2)]

# ==============================
# Extra Pie Chart
# ==============================
st.subheader("📊 Market-wise Delay & Zero-Interval Pie")

zero_intervals = (df_delay[interval_cols] == 0).sum(axis=1)
df_delay["Zero Intervals"] = zero_intervals

pie_data = df_delay.groupby("market").agg({
    "Zero Intervals": "sum",
    **{col: "mean" for col in interval_cols}
}).reset_index()

pie_data["Avg Delay"] = pie_data[[col for col in interval_cols]].mean(axis=1)

fig_pie = px.pie(pie_data, names="market", values="Avg Delay", title="Average Delay by Market")
st.plotly_chart(fig_pie, use_container_width=True)

fig_pie2 = px.pie(pie_data, names="market", values="Zero Intervals", title="Zero Interval Counts by Market")
st.plotly_chart(fig_pie2, use_container_width=True)
