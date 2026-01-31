import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.resource import ResourceManagementClient
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
    """
    deployments = []
    try:
        token = credential.get_token("https://management.azure.com/.default").token
        headers = {"Authorization": f"Bearer {token}"}
        
        api_version = "2023-05-01"
        url = f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices/accounts/{account_name}/deployments?api-version={api_version}"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            items = response.json().get('value', [])
            for item in items:
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

def fetch_actual_costs(credential, subscription_id, resource_ids, days=7):
    """
    Fetches REAL billing data from Azure Cost Management API.
    Note: Requires 'Cost Management Reader' permission.
    """
    cost_data = []
    error_msg = None
    
    try:
        token = credential.get_token("https://management.azure.com/.default").token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Scope is Subscription Level (we filter by ResourceId in body)
        url = f"https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query?api-version=2023-11-01"
        
        # Calculate Timeframe
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Payload for Cost Query
        # We group by ResourceId to match our Inventory
        payload = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {
                "from": start_date.strftime("%Y-%m-%dT00:00:00+00:00"),
                "to": end_date.strftime("%Y-%m-%dT00:00:00+00:00")
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "totalCost": {"name": "Cost", "function": "Sum"}
                },
                "grouping": [
                    {"type": "Dimension", "name": "ResourceId"},
                    {"type": "Dimension", "name": "ServiceName"}
                ],
                "filter": {
                    "dimensions": {
                        "name": "ResourceId",
                        "operator": "In",
                        "values": resource_ids
                    }
                }
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            # Rows: [Cost, Currency, ResourceId, ServiceName, Date]
            rows = result.get('properties', {}).get('rows', [])
            for r in rows:
                cost_data.append({
                    "Date": r[4], # Date is usually index 4 or 3 depending on API version
                    "ResourceId": r[2],
                    "ActualCost": r[0],
                    "Currency": r[1]
                })
        elif response.status_code == 403:
            error_msg = "⚠️ Permission Denied: Your account does not have 'Cost Management Reader' access."
        else:
            error_msg = f"Cost API Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        error_msg = f"Failed to fetch costs: {str(e)}"
        
    return pd.DataFrame(cost_data), error_msg

def discover_resources_and_deployments(credential, subscription_id, resource_group=None, hub_name=None):
    """
    Finds OpenAI accounts, then drills down to find Deployments (Models).
    """
    logs = []
    resource_client = ResourceManagementClient(credential, subscription_id)
    found_accounts_list = []
    
    try:
        if resource_group:
            logs.append(f"Scanning RG '{resource_group}'...")
            res_iter = resource_client.resources.list_by_resource_group(
                resource_group_name=resource_group,
                filter="resourceType eq 'Microsoft.CognitiveServices/accounts'"
            )
        else:
            logs.append("Scanning Subscription...")
            res_iter = resource_client.resources.list(
                filter="resourceType eq 'Microsoft.CognitiveServices/accounts'"
            )

        for res in res_iter:
            if hasattr(res, 'kind') and ('OpenAI' in res.kind or 'CognitiveServices' in res.kind):
                rg = res.id.split('/')[4]
                found_accounts_list.append({
                    "id": res.id,
                    "name": res.name,
                    "group": rg
                })
    except Exception as e:
        logs.append(f"Error scanning resources: {e}")

    final_inventory = []
    if found_accounts_list:
        pbar = st.progress(0)
        
    for i, acct in enumerate(found_accounts_list):
        logs.append(f"Inspecting account: {acct['name']}")
        depts = get_deployments(credential, subscription_id, acct['group'], acct['name'])
        
        if not depts:
            final_inventory.append({
                **acct,
                "deployment_name": "All Models (Aggregated)",
                "model_name": "unknown",
                "type": "text"
            })
        else:
            for d in depts:
                m_name = d['model_name'].lower()
                if "dall" in m_name: m_type = "image"
                elif "o1" in m_name or "reasoning" in m_name: m_type = "reasoning"
                elif "embedding" in m_name: m_type = "embedding"
                else: m_type = "text"

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
    client = MonitorManagementClient(credential, subscription_id)
    metric_names = "ProcessedPromptTokens,GeneratedTokens,GeneratedImages"
    endtime = datetime.utcnow()
    starttime = endtime - timedelta(days=days)
    timespan = f"{starttime.isoformat()}/{endtime.isoformat()}"

    data_rows = []
    errors = []
    grouped_inventory = {}
    for item in inventory_list:
        if item['id'] not in grouped_inventory: grouped_inventory[item['id']] = []
        grouped_inventory[item['id']].append(item)

    progress_bar = st.progress(0)
    total_steps = len(grouped_inventory)
    current_step = 0

    for account_id, deployments in grouped_inventory.items():
        try:
            for dept in deployments:
                dept_name = dept['deployment_name']
                is_agg = dept_name == "All Models (Aggregated)"
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
                                    "ResourceId": account_id,
                                    "Deployment": dept_name,
                                    "Model": dept['model_name'],
                                    "Type": dept['type'],
                                    "Metric": metric_name,
                                    "Value": data.total
                                })
        except Exception as e:
            if "BadRequest" not in str(e): errors.append(f"Error {account_id.split('/')[-1]}: {str(e)}")
        
        current_step += 1
        progress_bar.progress(current_step / total_steps)
        
    progress_bar.empty()
    return pd.DataFrame(data_rows), errors

def generate_demo_data_detailed(days=7):
    # Generates fake usage AND fake cost data for demo
    dates = pd.date_range(end=datetime.now(), periods=days*24, freq='H')
    data = []
    
    models = [
        {"name": "gpt-4", "type": "text", "dept": "gpt-4-deployment"},
        {"name": "gpt-35-turbo", "type": "text", "dept": "chat-deployment"},
        {"name": "dall-e-3", "type": "image", "dept": "img-gen"}
    ]
    
    for date in dates:
        hour_mod = 10 if 9 <= date.hour <= 17 else 1
        for m in models:
            if m['type'] == 'image':
                val = int(random.random() * 5 * hour_mod) if hour_mod > 1 else 0
                if val > 0:
                    data.append({
                        "TimeStamp": date, 
                        "Model": m['name'], 
                        "Type": "image", 
                        "Metric": "GeneratedImages", 
                        "Value": val, 
                        "Deployment": m['dept'], 
                        "ResourceId": "demo-id",
                        "Account": "Demo Account" # Added missing field
                    })
            else:
                prompts = int(random.gauss(500, 100) * hour_mod)
                gens = int(random.gauss(200, 50) * hour_mod)
                if prompts > 0:
                    data.append({
                        "TimeStamp": date, 
                        "Model": m['name'], 
                        "Type": m['type'], 
                        "Metric": "ProcessedPromptTokens", 
                        "Value": prompts, 
                        "Deployment": m['dept'], 
                        "ResourceId": "demo-id",
                        "Account": "Demo Account" # Added missing field
                    })
                    data.append({
                        "TimeStamp": date, 
                        "Model": m['name'], 
                        "Type": m['type'], 
                        "Metric": "GeneratedTokens", 
                        "Value": gens, 
                        "Deployment": m['dept'], 
                        "ResourceId": "demo-id",
                        "Account": "Demo Account" # Added missing field
                    })
    
    # Fake Cost Data
    cost_data = []
    unique_days = sorted(list(set([d.date() for d in dates])))
    for d in unique_days:
        cost_data.append({"Date": str(d), "ActualCost": random.uniform(5, 50), "Currency": "USD", "ResourceId": "demo-id"})
        
    return pd.DataFrame(data), pd.DataFrame(cost_data)

# --- UI LAYOUT ---

st.title("🌱 Azure GenAI Eco-Monitor")
st.caption("Real Cost, CO₂ Analysis & Power BI Bridge")

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
    df_cost = pd.DataFrame()
    debug_logs = []
    errors = []
    cost_error = None
    
    if mode == "Demo Data":
        df_raw, df_cost = generate_demo_data_detailed(days_to_fetch)
        
    elif mode == "Auto-Discovery":
        if not sub_id:
            st.error("Please provide Subscription ID.")
        else:
            credential = get_azure_credentials()
            if credential:
                with st.spinner("🔍 Scanning for Accounts & Deployments..."):
                    inventory, debug_logs = discover_resources_and_deployments(credential, sub_id, rg_name if 'rg_name' in locals() and rg_name else None)
                
                if inventory:
                    st.success(f"✅ Found {len(inventory)} deployments.")
                    
                    # 1. Fetch Metrics
                    with st.spinner("📊 Fetching usage metrics..."):
                        df_raw, errors = fetch_detailed_metrics(credential, sub_id, inventory, days_to_fetch)
                    
                    # 2. Fetch Costs
                    with st.spinner("💰 Fetching real billing data..."):
                        # Extract unique resource IDs to query cost
                        unique_res_ids = list(set([item['id'] for item in inventory]))
                        df_cost, cost_error = fetch_actual_costs(credential, sub_id, unique_res_ids, days_to_fetch)
                else:
                    st.warning("No OpenAI resources found.")

    elif mode == "Manual Input":
        if sub_id and rg_name and res_name:
            credential = get_azure_credentials()
            inv = [{"id": f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.CognitiveServices/accounts/{res_name}", 
                    "name": res_name, "deployment_name": "All Models (Aggregated)", "model_name": "Manual", "type": "text"}]
            df_raw, errors = fetch_detailed_metrics(credential, sub_id, inv, days_to_fetch)
            df_cost, cost_error = fetch_actual_costs(credential, sub_id, [inv[0]['id']], days_to_fetch)

    # --- PROCESSING ---
    if show_debug:
        with st.expander("Logs"):
            for l in debug_logs: st.text(l)
            if cost_error: st.warning(cost_error)

    if not df_raw.empty:
        # Calculate Energy/Carbon
        def calc_kwh(row):
            factor = CARBON_FACTORS.get("standard_text", 0.0004)
            if row['Type'] == 'image': return row['Value'] * CARBON_FACTORS['image_gen']
            elif row['Type'] == 'reasoning': factor = CARBON_FACTORS['reasoning_text']
            elif row['Type'] == 'embedding': factor = CARBON_FACTORS['embedding']
            return (row['Value'] / 1000) * factor

        df_raw['kWh'] = df_raw.apply(calc_kwh, axis=1)
        df_raw['Carbon_g'] = df_raw['kWh'] * grid_intensity
        
        # Totals
        total_co2 = df_raw['Carbon_g'].sum()
        tree_days = total_co2 / GRAMS_CO2_PER_TREE_DAY
        
        # COST LOGIC
        real_cost = 0
        cost_source = "Estimated"
        if not df_cost.empty:
            real_cost = pd.to_numeric(df_cost['ActualCost']).sum()
            cost_source = "Actual (Billed)"
        else:
            # Fallback Estimate
            real_cost = (df_raw[df_raw['Type']!='image']['Value'].sum()/1000 * 0.03) # Generic blended rate
        
        # --- KPI DISPLAY ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Carbon", f"{total_co2:.1f} gCO₂e")
        c2.metric(f"Total Cost ({cost_source})", f"${real_cost:,.2f}")
        c3.metric("Tree Offset", f"{tree_days:.1f} Days")
        c4.metric("Models Tracked", f"{len(df_raw['Model'].unique())}")
        
        if cost_error:
            st.caption(f"Note: Using estimated cost. {cost_error}")

        st.markdown("---")
        
        # --- POWER BI EXPORT ---
        # Prepare a clean single table for PowerBI
        st.subheader("📊 Export & Visualize")
        
        # Group metrics for cleaner export
        df_export = df_raw.groupby(['TimeStamp', 'Account', 'Model', 'Type']).agg({
            'Value': 'sum',
            'Carbon_g': 'sum',
            'kWh': 'sum'
        }).reset_index()
        
        csv_data = df_export.to_csv(index=False).encode('utf-8')
        
        col_pbi, col_info = st.columns([1, 2])
        with col_pbi:
            st.download_button(
                label="📥 Download Data for Power BI",
                data=csv_data,
                file_name="azure_genai_sustainability.csv",
                mime="text/csv",
                help="Import this CSV into Power BI Desktop to build custom reports."
            )
        with col_info:
            st.info("To use in Power BI: Open Power BI Desktop > Get Data > Text/CSV > Select this file.")

        # --- TABS ---
        tab_main, tab_cost = st.tabs(["🚀 Usage & Carbon", "💰 Cost Analysis"])
        
        with tab_main:
            # Usage Charts
            st.subheader("Carbon Emissions by Model")
            fig_bar = px.bar(df_raw.groupby("Model")["Carbon_g"].sum().reset_index(), x="Model", y="Carbon_g", title="Emissions (gCO2e)")
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with tab_cost:
            if not df_cost.empty:
                st.subheader("Daily Billed Cost")
                st.dataframe(df_cost)
                fig_cost = px.bar(df_cost, x="Date", y="ActualCost", title="Daily Spend (USD)")
                st.plotly_chart(fig_cost, use_container_width=True)
            else:
                st.warning("No billing data available. Ensure you have 'Cost Management Reader' permissions.")
                
    elif not show_debug:
        st.info("No usage data found.")