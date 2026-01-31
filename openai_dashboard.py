import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from azure.mgmt.monitor import MonitorManagementClient
import random

# Page Configuration
st.set_page_config(
    page_title="Azure OpenAI Usage Monitor",
    page_icon="🧠",
    layout="wide"
)

# Custom CSS for a professional look
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #0078D4;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .stMetric {
        background-color: white;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_azure_credentials():
    """
    Authenticates using DefaultAzureCredential. 
    If that fails (no CLI/Env vars), falls back to InteractiveBrowserCredential.
    """
    try:
        # 1. Try silent authentication (Env vars, Managed Identity, Azure CLI)
        credential = DefaultAzureCredential()
        # Probe to see if it actually works
        credential.get_token("https://management.azure.com/.default")
        return credential
    except Exception:
        # 2. Fallback to interactive browser login
        try:
            # This will open a browser window for the user to login
            credential = InteractiveBrowserCredential()
            return credential
        except Exception as e:
            st.error(f"Authentication failed: {e}. Please ensure you have internet access or try installing Azure CLI and running 'az login'.")
            return None

def fetch_metrics(subscription_id, resource_group, resource_name, days=7, demo_mode=False):
    """
    Fetches real metrics from Azure Monitor or generates demo data.
    Metrics: ProcessedInferenceTokens, ProcessedPromptTokens, GeneratedCompletionTokens
    """
    
    # --- DEMO MODE GENERATOR ---
    if demo_mode:
        dates = pd.date_range(end=datetime.now(), periods=days*24, freq='H')
        data = []
        for date in dates:
            # Simulate daily working hours spike
            hour_modifier = 10 if 9 <= date.hour <= 17 else 1
            prompts = int(random.gauss(1000, 300) * hour_modifier)
            completions = int(random.gauss(500, 150) * hour_modifier)
            if prompts < 0: prompts = 0
            if completions < 0: completions = 0
            
            data.append({
                "TimeStamp": date,
                "Prompt Tokens": prompts,
                "Completion Tokens": completions,
                "Total Tokens": prompts + completions,
                "Latency (ms)": random.uniform(200, 800)
            })
        return pd.DataFrame(data)

    # --- REAL AZURE FETCHING ---
    credential = get_azure_credentials()
    if not credential:
        st.error("Could not obtain credentials.")
        return pd.DataFrame()

    client = MonitorManagementClient(credential, subscription_id)
    resource_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices/accounts/{resource_name}"
    
    # Azure Metric Names
    metric_names = "ProcessedPromptTokens,GeneratedCompletionTokens"
    
    # Time format for Azure
    endtime = datetime.utcnow()
    starttime = endtime - timedelta(days=days)
    timespan = f"{starttime.isoformat()}/{endtime.isoformat()}"

    try:
        metrics_data = client.metrics.list(
            resource_uri=resource_id,
            timespan=timespan,
            interval="PT1H", # Hourly granularity
            metricnames=metric_names,
            aggregation="Total"
        )
    except Exception as e:
        st.error(f"Failed to fetch data from Azure: {e}")
        st.info("Check your Subscription ID and Resource details.")
        return pd.DataFrame()

    # Parse Azure response into DataFrame
    records = {}
    
    for item in metrics_data.value:
        metric_name = item.name.value
        for timeseries in item.timeseries:
            for data in timeseries.data:
                ts = data.time_stamp
                val = data.total if data.total is not None else 0
                
                if ts not in records:
                    records[ts] = {"TimeStamp": ts, "Prompt Tokens": 0, "Completion Tokens": 0}
                
                if metric_name == "ProcessedPromptTokens":
                    records[ts]["Prompt Tokens"] = val
                elif metric_name == "GeneratedCompletionTokens":
                    records[ts]["Completion Tokens"] = val

    df = pd.DataFrame(list(records.values()))
    if not df.empty:
        df["Total Tokens"] = df["Prompt Tokens"] + df["Completion Tokens"]
        df["TimeStamp"] = pd.to_datetime(df["TimeStamp"])
        df = df.sort_values("TimeStamp")
    
    return df

# --- UI LAYOUT ---

st.title("📊 Azure GenAI Usage Dashboard")
st.markdown("Visualize your LLM consumption, token distribution, and trends.")

# Sidebar for Configuration
with st.sidebar:
    st.header("🔌 Connection Settings")
    
    mode = st.radio("Data Source", ["Demo Data (Test View)", "Connect to Azure"])
    
    if mode == "Connect to Azure":
        st.info("Ensure you are logged in. If CLI is missing, a browser window will open.")
        sub_id = st.text_input("Subscription ID", type="password")
        rg_name = st.text_input("Resource Group")
        res_name = st.text_input("OpenAI Resource Name")
        days_to_fetch = st.slider("Days history", 1, 30, 7)
        
        fetch_btn = st.button("Fetch Data")
        demo = False
    else:
        fetch_btn = True # Always show in demo mode
        demo = True
        days_to_fetch = 7
        sub_id, rg_name, res_name = "", "", ""

# Main Logic
if fetch_btn:
    with st.spinner('Loading usage metrics...'):
        df = fetch_metrics(sub_id, rg_name, res_name, days_to_fetch, demo_mode=demo)

    if not df.empty:
        # 1. Top Level KPIs
        total_prompts = df["Prompt Tokens"].sum()
        total_completions = df["Completion Tokens"].sum()
        total_usage = df["Total Tokens"].sum()
        
        # Calculate cost estimate (Rough approximation based on generic GPT-4o pricing)
        # $5.00 / 1M input, $15.00 / 1M output
        est_cost = (total_prompts/1_000_000 * 5) + (total_completions/1_000_000 * 15)

        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Tokens Processed", f"{total_usage:,.0f}", delta=f"Last {days_to_fetch} days")
        with col2:
            st.metric("Prompt (Input) Tokens", f"{total_prompts:,.0f}", f"{total_prompts/total_usage:.1%} of total")
        with col3:
            st.metric("Completion (Output) Tokens", f"{total_completions:,.0f}", f"{total_completions/total_usage:.1%} of total")
        with col4:
            st.metric("Est. Cost (GPT-4o rates)", f"${est_cost:,.2f}")

        st.markdown("---")

        # 2. Main Visualization Area
        tab1, tab2 = st.tabs(["📈 Token Trends", "⚖️ Input vs Output"])

        with tab1:
            st.subheader("Usage Over Time")
            fig_line = px.area(
                df, 
                x="TimeStamp", 
                y=["Prompt Tokens", "Completion Tokens"],
                title="Token Consumption (Hourly)",
                color_discrete_map={"Prompt Tokens": "#0078D4", "Completion Tokens": "#00CC6A"}
            )
            fig_line.update_layout(xaxis_title="Time", yaxis_title="Token Count")
            st.plotly_chart(fig_line, use_container_width=True)

        with tab2:
            st.subheader("Prompt vs Completion Ratio")
            col_a, col_b = st.columns(2)
            
            with col_a:
                # Pie Chart
                usage_summary = pd.DataFrame({
                    "Type": ["Prompt (Input)", "Completion (Output)"],
                    "Count": [total_prompts, total_completions]
                })
                fig_pie = px.pie(
                    usage_summary, 
                    values="Count", 
                    names="Type", 
                    color="Type",
                    color_discrete_map={"Prompt (Input)": "#0078D4", "Completion (Output)": "#00CC6A"},
                    hole=0.4
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_b:
                st.info("""
                **Why this matters:**
                
                - **High Input %:** Typical for RAG (Retrieval Augmented Generation) where you send lots of documents as context but get short answers.
                - **High Output %:** Typical for creative writing or code generation where you give a short instruction and get a long result.
                """)

        # 3. Raw Data Explorer
        with st.expander("🔎 View Raw Data"):
            st.dataframe(df.sort_values("TimeStamp", ascending=False), use_container_width=True)

    else:
        if not demo:
            st.warning("No data found. Please check your Subscription ID and Resource Name.")