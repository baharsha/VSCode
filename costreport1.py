import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.resource import ResourceManagementClient
# REMOVED: from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
import random

# Page Configuration
st.set_page_config(
    page_title="Azure GenAI Eco-Monitor",
    page_icon="🌱",
    layout="wide"
)

# Custom CSS
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

# --- CARBON & ENERGY CONSTANTS ---
# Grid Intensity (gCO2/kWh)
REGION_INTENSITY = {
    "Global Average": 475,
    "US East (Virginia)": 350,
    "US West (California)": 200,
    "Europe (Ireland)": 280,
    "Europe (Sweden)": 20,
    "Asia (average)": 550
}

# Energy Factors (kWh per unit)
CARBON_FACTORS = {
    "standard_text": 0.0004,   # kWh per 1k tokens (GPT-3.5/4 class)
    "reasoning_text": 0.0015,  # kWh per 1k tokens (o1 class - higher due to CoT)
    "image_gen": 0.05,         # kWh per IMAGE (DALL-E 3 class - high compute)
    "embedding": 0.0001        # kWh per 1k tokens (lighter)
}

# Tree Absorption: ~21kg CO2 per year = ~57.5g per day
GRAMS_CO2_PER_TREE_DAY = 57.5

@st.cache_resource
def get_azure_credentials():
    """Authenticates using Default or Interactive credentials."""
    try:
        credential = DefaultAzureCredential()
        credential.get_token("https://management.azure.com/.default")
        return credential
    except Exception as e:
        print(f"DefaultAuth failed: {e}")
        try:
            return InteractiveBrowserCredential()
        except Exception as e2:
            st.error(f"Authentication failed: {e2}")
            return None

def get_deployments(credential, subscription_id, resource_group, account_name):
    """
    Fetches the list of deployments (models) for a specific OpenAI account.
    Uses direct REST API to avoid needing the extra azure-mgmt-cognitiveservices library.
    """
    deployments = []
    try:
        # Get Auth Token
        token = credential.get_token("https://management.azure.com/.default").token
        headers = {"Authorization": f"Bearer {token}"}
        
        # Azure Management API for Deployments
        api_version = "2023-05-01"
        url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices/accounts/{account_name}/deployments?api-version={api_version}"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            items = response.json().get('value', [])
            for item in items:
                # Parse properties safely
                props = item.get('properties', {})
                model_info = props.get('model', {})
                
                deployments.append({
                    "deployment_name": item.get('name'),
                    "model_name": model_info.get('name', 'unknown'),
                    "model_version": model_info.get('version', ''),
                    "model_format": model_info.get('format', '')
                })
        else:
            print(f"Failed to list deployments for {account_name}: {response.status_code}")
            
    except Exception as e:
        print(f"Error listing deployments: {e}")
        
    return deployments

def discover_resources_and_deployments(credential, subscription_id, resource_group=None, hub_name=None):
    """
    Finds OpenAI accounts, then drills down to find Deployments (Models) within them.
    """
    logs = []
    resource_client = ResourceManagementClient(credential, subscription_id)

    # 1. Find Accounts (Hub or RG or Subscription)
    found_accounts_list = []
    
    try:
        if resource_group:
            logs.append(f"Scanning RG '{resource_group}' for OpenAI accounts...")
            res_iter = resource_client.resources.list_by_resource_group(
                resource_group_name=resource_group,
                filter="resourceType eq 'Microsoft.CognitiveServices/accounts'"
            )
        else:
            logs.append("Scanning Subscription for OpenAI accounts...")
            res_iter = resource_client.resources.list(
                filter="resourceType eq 'Microsoft.CognitiveServices/accounts'"
            )

        for res in res_iter:
            # Check if it's actually OpenAI kind (or CogServices generic)
            if hasattr(res, 'kind') and ('OpenAI' in res.kind or 'CognitiveServices' in res.kind):
                # ID format: /subscriptions/{sub}/resourceGroups/{rg}/...
                rg = res.id.split('/')[4]
                found_accounts_list.append({
                    "id": res.id,
                    "name": res.name,
                    "group": rg
                })
    except Exception as e:
        logs.append(f"Error scanning resources: {e}")

    # 2. Drill down into Deployments per Account
    final_inventory = []
    
    # Show progress bar if we have many accounts
    if found_accounts_list:
        pbar = st.progress(0)
        
    for i, acct in enumerate(found_accounts_list):
        logs.append(f"Inspecting account: {acct['name']}")
        depts = get_deployments(credential, subscription_id, acct['group'], acct['name'])
        
        if not depts:
            # If no deployments found, add a "General" placeholder
            final_inventory.append({
                **acct,
                "deployment_name": "All Models (Aggregated)",
                "model_name": "unknown",
                "type": "text"
            })
        else:
            for d in depts:
                # Determine type for carbon math
                m_name = d['model_name'].lower()
                if "dall" in m_name:
                    m_type = "image"
                elif "o1" in m_name or "reasoning" in m_name:
                    m_type = "reasoning"
                elif "embedding" in m_name:
                    m_type = "embedding"
                else:
                    m_type = "text"

                final_inventory.append({
                    **acct,
                    "deployment_name": d['deployment_name'],
                    "model_name": d['model_name'],
                    "type": m_type
                })
        
        if found_accounts_list:
            pbar.progress((i + 1) / len(found_accounts_list))
            
    if found_accounts_list:
        pbar.empty()
                
    return final_inventory, logs

def fetch_detailed_metrics(credential, subscription_id, inventory_list, days=7):
    """
    Fetches usage metrics filtered by Deployment Name to get per-model granularity.
    """
    client = MonitorManagementClient(credential, subscription_id)
    
    # Metrics: 'GeneratedImages' (DALL-E), 'ProcessedPromptTokens'/'GeneratedTokens' (Text)
    metric_names = "ProcessedPromptTokens,GeneratedTokens,GeneratedImages"
    
    endtime = datetime.utcnow()
    starttime = endtime - timedelta(days=days)
    timespan = f"{starttime.isoformat()}/{endtime.isoformat()}"

    data_rows = []
    errors = []
    
    # Group by Account ID to minimize client calls
    grouped_inventory = {}
    for item in inventory_list:
        if item['id'] not in grouped_inventory:
            grouped_inventory[item['id']] = []
        grouped_inventory[item['id']].append(item)

    progress_bar = st.progress(0)
    total_steps = len(grouped_inventory)
    current_step = 0

    for account_id, deployments in grouped_inventory.items():
        try:
            for dept in deployments:
                dept_name = dept['deployment_name']
                is_agg = dept_name == "All Models (Aggregated)"
                
                # Filter syntax for Azure Monitor
                odata_filter = f"ModelDeploymentName eq '{dept_name}'" if not is_agg else None
                
                metrics_data = client.metrics.list(
                    resource_uri=account_id,
                    timespan=timespan,
                    interval="PT1H",
                    metricnames=metric_names,
                    aggregation="Total",
                    filter=odata_filter 
                )
                
                for item in metrics_data.value:
                    metric_name = item.name.value
                    for timeseries in item.timeseries:
                        for data in timeseries.data:
                            if data.total and data.total > 0:
                                data_rows.append({
                                    "TimeStamp": data.time_stamp,
                                    "Account": dept['name'],
                                    "Deployment": dept_name,
                                    "Model": dept['model_name'],
                                    "Type": dept['type'],
                                    "Metric": metric_name,
                                    "Value": data.total
                                })

        except Exception as e:
            if "BadRequest" not in str(e): 
                errors.append(f"Error {account_id.split('/')[-1]}: {str(e)}")
        
        current_step += 1
        progress_bar.progress(current_step / total_steps)
        
    progress_bar.empty()
    return pd.DataFrame(data_rows), errors

def generate_demo_data_detailed(days=7):
    dates = pd.date_range(end=datetime.now(), periods=days*24, freq='H')
    data = []
    
    models = [
        {"name": "gpt-4", "type": "text", "dept": "gpt-4-deployment"},
        {"name": "gpt-35-turbo", "type": "text", "dept": "chat-deployment"},
        {"name": "o1-preview", "type": "reasoning", "dept": "reasoning-dept"},
        {"name": "dall-e-3", "type": "image", "dept": "img-gen"}
    ]
    
    for date in dates:
        hour_mod = 10 if 9 <= date.hour <= 17 else 1
        
        for m in models:
            if m['type'] == 'image':
                val = int(random.random() * 5 * hour_mod) if hour_mod > 1 else 0
                if val > 0:
                    data.append({"TimeStamp": date, "Model": m['name'], "Type": "image", "Metric": "GeneratedImages", "Value": val, "Deployment": m['dept']})
            else:
                prompts = int(random.gauss(500, 100) * hour_mod)
                gens = int(random.gauss(200, 50) * hour_mod)
                if prompts > 0:
                    data.append({"TimeStamp": date, "Model": m['name'], "Type": m['type'], "Metric": "ProcessedPromptTokens", "Value": prompts, "Deployment": m['dept']})
                    data.append({"TimeStamp": date, "Model": m['name'], "Type": m['type'], "Metric": "GeneratedTokens", "Value": gens, "Deployment": m['dept']})
                    
    return pd.DataFrame(data)

# --- UI LAYOUT ---

st.title("🌱 Azure GenAI Eco-Monitor")
st.caption("Detailed breakdown: Per Model, Per Feature (Text/Image/Audio)")

# Sidebar
with st.sidebar:
    st.header("🔌 Connection")
    mode = st.radio("Mode", ["Demo Data", "Auto-Discovery", "Manual Input"])
    
    st.header("🌍 Parameters")
    selected_region = st.selectbox("Region", list(REGION_INTENSITY.keys()))
    grid_intensity = REGION_INTENSITY[selected_region]
    
    if mode == "Auto-Discovery":
        sub_id = st.text_input("Subscription ID", type="password")
        with st.expander("Filter Scope (Optional)"):
             rg_name = st.text_input("Resource Group Name")
        days_to_fetch = st.slider("Days history", 1, 30, 7)
        show_debug = st.checkbox("Show Debug Logs")
        fetch_btn = st.button("Discover & Analyze")
        
    elif mode == "Manual Input":
        sub_id = st.text_input("Subscription ID", type="password")
        rg_name = st.text_input("Resource Group")
        res_name = st.text_input("OpenAI Resource Name")
        days_to_fetch = st.slider("Days history", 1, 30, 7)
        fetch_btn = st.button("Fetch Data")
        show_debug = False
    else:
        fetch_btn = True
        days_to_fetch = 7
        sub_id = ""
        show_debug = False

if fetch_btn:
    df_raw = pd.DataFrame()
    debug_logs = []
    errors = []
    
    if mode == "Demo Data":
        df_raw = generate_demo_data_detailed(days_to_fetch)
        
    elif mode == "Auto-Discovery":
        if not sub_id:
            st.error("Please provide Subscription ID.")
        else:
            credential = get_azure_credentials()
            if credential:
                with st.spinner("🔍 Scanning for Accounts & Deployments..."):
                    inventory, debug_logs = discover_resources_and_deployments(credential, sub_id, rg_name if 'rg_name' in locals() and rg_name else None)
                
                if inventory:
                    st.success(f"✅ Found {len(inventory)} model deployments across your resources.")
                    with st.expander("See Inventory"):
                        st.dataframe(pd.DataFrame(inventory)[['name', 'deployment_name', 'model_name', 'type']])
                    
                    with st.spinner("📊 Fetching metrics per model..."):
                        df_raw, errors = fetch_detailed_metrics(credential, sub_id, inventory, days_to_fetch)
                else:
                    st.warning("No OpenAI resources found.")

    elif mode == "Manual Input":
        if sub_id and rg_name and res_name:
            credential = get_azure_credentials()
            inv = [{"id": f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.CognitiveServices/accounts/{res_name}", 
                    "name": res_name, "deployment_name": "All Models (Aggregated)", "model_name": "Manual", "type": "text"}]
            df_raw, errors = fetch_detailed_metrics(credential, sub_id, inv, days_to_fetch)

    # --- PROCESSING & VISUALIZATION ---
    if show_debug and (debug_logs or errors):
        with st.expander("Logs"):
            for l in debug_logs: st.text(l)
            for e in errors: st.error(e)

    if not df_raw.empty:
        # 1. Calculate Energy & Carbon PER ROW
        def calc_kwh(row):
            factor = CARBON_FACTORS.get("standard_text", 0.0004)
            if row['Type'] == 'image':
                return row['Value'] * CARBON_FACTORS['image_gen']
            elif row['Type'] == 'reasoning':
                factor = CARBON_FACTORS['reasoning_text']
            elif row['Type'] == 'embedding':
                factor = CARBON_FACTORS['embedding']
            return (row['Value'] / 1000) * factor

        df_raw['kWh'] = df_raw.apply(calc_kwh, axis=1)
        df_raw['Carbon_g'] = df_raw['kWh'] * grid_intensity
        
        total_co2 = df_raw['Carbon_g'].sum()
        total_kwh = df_raw['kWh'].sum()
        
        # Tree Calculations
        # How many days would 1 tree need to work to offset this?
        tree_days = total_co2 / GRAMS_CO2_PER_TREE_DAY
        
        # KPI Row
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Carbon Footprint", f"{total_co2:.1f} gCO₂e", help=f"Based on {selected_region} grid intensity.")
        c2.metric("Total Energy", f"{total_kwh:.3f} kWh")
        c3.metric("Tree Offset", f"{tree_days:.1f} Tree-Days", help="Days required for 1 mature tree to absorb this amount (approx 57g/day).")
        c4.metric("Datapoints Fetched", f"{len(df_raw)}")
        
        st.markdown("---")
        
        # 3. TABS
        tab_models, tab_features, tab_data = st.tabs(["🤖 Emissions by Model", "🎨 Features (Text vs Image)", "📄 Data"])
        
        with tab_models:
            st.subheader("Which model is the heaviest emitter?")
            
            # Group by Model and sum Carbon
            df_model = df_raw.groupby("Model")[["Carbon_g", "Value"]].sum().reset_index()
            df_model = df_model.sort_values("Carbon_g", ascending=False)
            
            col_chart, col_details = st.columns([2, 1])
            
            with col_chart:
                fig_bar = px.bar(
                    df_model, 
                    x="Model", 
                    y="Carbon_g", 
                    color="Model", 
                    title="Total Carbon Emissions by Model",
                    text_auto='.1f'
                )
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with col_details:
                st.write("**Breakdown:**")
                st.dataframe(df_model, hide_index=True)

        with tab_features:
            st.subheader("Usage Type Breakdown")
            df_img = df_raw[df_raw['Metric'] == 'GeneratedImages']
            df_text = df_raw[df_raw['Metric'].isin(['ProcessedPromptTokens', 'GeneratedTokens'])]
            
            c_a, c_b = st.columns(2)
            with c_a:
                st.markdown("#### 📝 Text Usage")
                if not df_text.empty:
                    fig_text = px.area(df_text, x="TimeStamp", y="Value", color="Metric", title="Token Volume Over Time")
                    st.plotly_chart(fig_text, use_container_width=True)
                else:
                    st.info("No text usage data.")
            with c_b:
                st.markdown("#### 🖼️ Image Generation")
                if not df_img.empty:
                    fig_img = px.bar(df_img, x="TimeStamp", y="Value", title="Images Generated (Count)")
                    st.plotly_chart(fig_img, use_container_width=True)
                else:
                    st.info("No image generation data.")

        with tab_data:
            st.dataframe(df_raw.sort_values("TimeStamp", ascending=False), use_container_width=True)
            
    elif not show_debug:
        st.info("No data returned. Check Debug Logs or ensure your models have traffic in the selected period.")