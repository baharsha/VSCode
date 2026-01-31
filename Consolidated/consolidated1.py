import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
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

# Approximate Exchange Rates for fallback conversion to SEK
EXCHANGE_RATES_TO_SEK = {
    "USD": 10.8,
    "EUR": 11.5,
    "GBP": 13.5,
    "SEK": 1.0
}

@st.cache_resource
def get_azure_credentials():
    """Authenticates using Default or Interactive credentials."""
    try:
        # 1. Try silent authentication (Managed Identity, Env Vars, Azure CLI)
        # exclude_interactive_browser_credential=True prevents it from trying to open a browser on the server immediately
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        # Probe to see if it actually works
        credential.get_token("https://management.azure.com/.default")
        return credential
    except Exception as e:
        # 2. Fallback to interactive browser login (ONLY works locally)
        try:
            credential = InteractiveBrowserCredential()
            # Probe to trigger the browser popup immediately inside this try block
            credential.get_token("https://management.azure.com/.default")
            return credential
        except Exception as e2:
            st.error(f"Authentication Failed: {e}")
            st.warning("""
            **Deployment Troubleshooting:**
            If you are seeing this on Azure Web App, it means **Managed Identity** failed.
            
            1. Go to **App Service > Settings > Identity** and ensure it is **On**.
            2. Go to **Azure role assignments** and ensure the app has **'Monitoring Reader'** permissions on the Subscription/Resource Group.
            3. Wait 10-15 minutes for permissions to propagate.
            """)
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
        # NOTE: Removed 'Currency' grouping as it causes 400 Bad Request in some scopes
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
                    {"type": "Dimension", "name": "ResourceId"}
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
            properties = result.get('properties', {})
            columns = properties.get('columns', [])
            rows = properties.get('rows', [])
            
            # Dynamic Column Mapping to handle API variations
            col_map = {c['name']: i for i, c in enumerate(columns)}
            
            for r in rows:
                # Fetch values dynamically
                cost_val = r[col_map.get('Cost', 0)]
                res_id = r[col_map.get('ResourceId', 1)]
                
                # Currency handling - usually returned even if not grouped
                curr_idx = col_map.get('Currency') 
                if curr_idx is None: curr_idx = col_map.get('BillingCurrency')
                curr = r[curr_idx] if curr_idx is not None else "USD" # Default fallback
                
                # Date handling
                date_idx = col_map.get('UsageDate')
                date_val = r[date_idx] if date_idx is not None else end_date
                
                # Normalize date
                if isinstance(date_val, int):
                    date_str = str(date_val)
                    date_obj = datetime.strptime(date_str, "%Y%m%d")
                else:
                    date_obj = pd.to_datetime(date_val)

                cost_data.append({
                    "Date": date_obj,
                    "ResourceId": res_id,
                    "ActualCost": cost_val,
                    "OriginalCurrency": curr
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
    Finds OpenAI accounts, then drills down to find Deployments (Models) within them.
    Also fetches Tags to identify Projects.
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
                filter="resourceType eq 'Microsoft.CognitiveServices/accounts'",
                expand="tags" # Ensure tags are returned
            )
        else:
            logs.append("Scanning Subscription for OpenAI accounts...")
            res_iter = resource_client.resources.list(
                filter="resourceType eq 'Microsoft.CognitiveServices/accounts'",
                expand="tags"
            )

        for res in res_iter:
            # Check if it's actually OpenAI kind (or CogServices generic)
            if hasattr(res, 'kind') and ('OpenAI' in res.kind or 'CognitiveServices' in res.kind):
                # ID format: /subscriptions/{sub}/resourceGroups/{rg}/...
                rg = res.id.split('/')[4]
                
                # Identify Project Name:
                # 1. Look for 'DigitalProduct' tag
                # 2. Look for 'Project' tag
                # 3. Fallback to Resource Group Name (Often matches project in Azure)
                tags = res.tags or {}
                project_name = tags.get('DigitalProduct') or tags.get('Project') or tags.get('Application') or rg
                
                found_accounts_list.append({
                    "id": res.id,
                    "name": res.name,
                    "group": rg,
                    "project": project_name,
                    "tags": tags
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
        
        # Prepare common info for inventory
        common_info = {
            "id": acct['id'],
            "name": acct['name'],
            "group": acct['group'],
            "project": acct['project'],
            "tags": acct['tags']
        }
        
        if not depts:
            # If no deployments found, add a "General" placeholder
            final_inventory.append({
                **common_info,
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
                    **common_info,
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
                                    "ResourceId": account_id,
                                    "Project": dept['project'], # Key addition
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
    
    # Demo Projects matching user patterns
    projects = [
        {"name": "VG-AZ-109460-SDAI-LABUSER", "model": "gpt-4", "type": "text", "res_name": "ai-res-01"},
        {"name": "113527-volvogpt", "model": "gpt-4", "type": "text", "res_name": "ai-res-02"},
        {"name": "rd-usecases", "model": "dall-e-3", "type": "image", "res_name": "ai-res-03"}
    ]
    
    for date in dates:
        hour_mod = 10 if 9 <= date.hour <= 17 else 1
        
        for p in projects:
            if p['type'] == 'image':
                val = int(random.random() * 5 * hour_mod) if hour_mod > 1 else 0
                if val > 0:
                    data.append({
                        "TimeStamp": date, "Model": p['model'], "Type": "image", "Metric": "GeneratedImages", 
                        "Value": val, "Deployment": "dep-1", 
                        "ResourceId": f"/subscriptions/s/resourceGroups/{p['name']}/providers/Microsoft.CognitiveServices/accounts/{p['res_name']}", 
                        "Account": p['res_name'], "Project": p['name']
                    })
            else:
                prompts = int(random.gauss(500, 100) * hour_mod)
                gens = int(random.gauss(200, 50) * hour_mod)
                if prompts > 0:
                    data.append({
                        "TimeStamp": date, "Model": p['model'], "Type": "text", "Metric": "ProcessedPromptTokens", 
                        "Value": prompts, "Deployment": "dep-1", 
                        "ResourceId": f"/subscriptions/s/resourceGroups/{p['name']}/providers/Microsoft.CognitiveServices/accounts/{p['res_name']}", 
                        "Account": p['res_name'], "Project": p['name']
                    })
                    data.append({
                        "TimeStamp": date, "Model": p['model'], "Type": "text", "Metric": "GeneratedTokens", 
                        "Value": gens, "Deployment": "dep-1", 
                        "ResourceId": f"/subscriptions/s/resourceGroups/{p['name']}/providers/Microsoft.CognitiveServices/accounts/{p['res_name']}", 
                        "Account": p['res_name'], "Project": p['name']
                    })
    
    # Fake Cost Data for Demo (SEK)
    cost_data = []
    unique_days = sorted(list(set([d.date() for d in dates])))
    for d in unique_days:
        for p in projects:
            cost_data.append({
                "Date": pd.to_datetime(d),
                "ActualCost": random.uniform(50, 500),
                "OriginalCurrency": "SEK",
                "ResourceId": f"/subscriptions/s/resourceGroups/{p['name']}/providers/Microsoft.CognitiveServices/accounts/{p['res_name']}"
            })
                    
    return pd.DataFrame(data), pd.DataFrame(cost_data)

# --- UI LAYOUT ---

st.title("🌱 Azure GenAI Eco-Monitor")
st.caption("Detailed breakdown: Cost (SEK), Carbon & Projects")

# Sidebar
with st.sidebar:
    st.header("🔌 Connection")
    mode = st.radio("Mode", ["Demo Data", "Auto-Discovery", "Manual Input"])
    
    st.header("🌍 Parameters")
    selected_region = st.selectbox("Region", list(REGION_INTENSITY.keys()))
    grid_intensity = REGION_INTENSITY[selected_region]
    
    st.header("💱 Currency Settings")
    st.caption("Exchange rates used if Azure returns USD/EUR.")
    usd_rate = st.number_input("USD to SEK Rate", value=10.8, step=0.1)
    
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
    
    # Need to keep inventory for cost mapping
    final_inventory = []
    
    if mode == "Demo Data":
        df_raw, df_cost = generate_demo_data_detailed(days_to_fetch)
        # Create fake inventory for mapping logic in cost tab
        for p in ["VG-AZ-109460-SDAI-LABUSER", "113527-volvogpt", "rd-usecases"]:
             # We just need ID -> Project mapping
             pass
        
    elif mode == "Auto-Discovery":
        if not sub_id:
            st.error("Please provide Subscription ID.")
        else:
            credential = get_azure_credentials()
            if credential:
                with st.spinner("🔍 Scanning for Accounts & Deployments..."):
                    final_inventory, debug_logs = discover_resources_and_deployments(credential, sub_id, rg_name if 'rg_name' in locals() and rg_name else None)
                
                if final_inventory:
                    st.success(f"✅ Found {len(final_inventory)} model deployments across your resources.")
                    
                    # 1. Fetch Carbon/Usage Metrics
                    with st.spinner("📊 Fetching usage metrics..."):
                        df_raw, errors = fetch_detailed_metrics(credential, sub_id, final_inventory, days_to_fetch)
                        
                    # 2. Fetch Cost Data
                    with st.spinner("💰 Fetching billing data..."):
                        unique_res_ids = list(set([item['id'] for item in final_inventory]))
                        if unique_res_ids:
                            df_cost, cost_error = fetch_actual_costs(credential, sub_id, unique_res_ids, days_to_fetch)
                else:
                    st.warning("No OpenAI resources found.")

    elif mode == "Manual Input":
        if sub_id and rg_name and res_name:
            credential = get_azure_credentials()
            # Manual assumes Name is Project for simplicity
            inv = [{"id": f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.CognitiveServices/accounts/{res_name}", 
                    "name": res_name, "deployment_name": "All Models (Aggregated)", "model_name": "Manual", "type": "text", 
                    "group": rg_name, "project": rg_name, "tags": {}}]
            final_inventory = inv
            df_raw, errors = fetch_detailed_metrics(credential, sub_id, inv, days_to_fetch)
            df_cost, cost_error = fetch_actual_costs(credential, sub_id, [inv[0]['id']], days_to_fetch)

    # --- PROCESSING & VISUALIZATION ---
    if show_debug and (debug_logs or errors):
        with st.expander("Logs"):
            for l in debug_logs: st.text(l)
            for e in errors: st.error(e)
            if cost_error: st.warning(cost_error)

    if not df_raw.empty:
        # 1. Carbon Calculations
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
        tree_days = total_co2 / GRAMS_CO2_PER_TREE_DAY
        
        # 2. Cost Processing (Currency Conversion to SEK)
        total_cost_sek = 0.0
        
        if not df_cost.empty:
            # Conversion Logic
            def convert_to_sek(row):
                curr = row['OriginalCurrency']
                val = row['ActualCost']
                if curr == "SEK": return val
                elif curr == "USD": return val * usd_rate
                elif curr == "EUR": return val * EXCHANGE_RATES_TO_SEK.get("EUR", 11.5)
                else: return val * EXCHANGE_RATES_TO_SEK.get(curr, 1.0)
            
            df_cost['CostSEK'] = df_cost.apply(convert_to_sek, axis=1)
            total_cost_sek = df_cost['CostSEK'].sum()
            
            # Map ResourceId to PROJECT NAME
            # Create mapping from inventory if available, else fallback to extracting RG
            if final_inventory:
                id_to_proj = {item['id']: item.get('project', item['group']) for item in final_inventory}
                df_cost['ProjectName'] = df_cost['ResourceId'].map(id_to_proj).fillna('Unknown')
            else:
                # If demo or manual, we might already have it or need to extract
                # Fallback extraction: Resource Group is usually the 4th segment in ID
                # /subscriptions/sub/resourceGroups/{RG_NAME}/...
                if 'Project' in df_cost.columns:
                     df_cost['ProjectName'] = df_cost['Project'] # From demo data
                else:
                     df_cost['ProjectName'] = df_cost['ResourceId'].apply(lambda x: x.split('/')[4] if isinstance(x, str) and len(x.split('/')) > 4 else 'Unknown')
        
        # KPI Row
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Carbon", f"{total_co2:.1f} gCO₂e", help=f"Region: {selected_region}")
        c2.metric("Total Cost", f"{total_cost_sek:,.2f} SEK", help="Aggregated from Azure Cost Management.")
        c3.metric("Tree Offset", f"{tree_days:.1f} Days", help="Days for 1 mature tree to absorb this.")
        c4.metric("Total Energy", f"{total_kwh:.3f} kWh")
        
        st.markdown("---")
        
        # 3. TABS
        tab_models, tab_features, tab_cost, tab_data = st.tabs(["🤖 Emissions by Model", "🎨 Features", "💰 Project Summary", "📄 Data"])
        
        with tab_models:
            st.subheader("Which model is the heaviest emitter?")
            df_model = df_raw.groupby("Model")[["Carbon_g", "Value"]].sum().reset_index()
            df_model = df_model.sort_values("Carbon_g", ascending=False)
            
            col_chart, col_details = st.columns([2, 1])
            with col_chart:
                fig_bar = px.bar(df_model, x="Model", y="Carbon_g", color="Model", title="Total Carbon (gCO2e)", text_auto='.1f')
                st.plotly_chart(fig_bar, use_container_width=True)
            with col_details:
                st.write("**Breakdown:**")
                st.dataframe(df_model, hide_index=True)

        with tab_features:
            c_a, c_b = st.columns(2)
            df_text = df_raw[df_raw['Metric'].isin(['ProcessedPromptTokens', 'GeneratedTokens'])]
            df_img = df_raw[df_raw['Metric'] == 'GeneratedImages']
            
            with c_a:
                st.markdown("#### 📝 Text Usage")
                if not df_text.empty:
                    fig_text = px.area(df_text, x="TimeStamp", y="Value", color="Metric", title="Token Volume")
                    st.plotly_chart(fig_text, use_container_width=True)
                else: st.info("No text usage.")
            with c_b:
                st.markdown("#### 🖼️ Image Generation")
                if not df_img.empty:
                    fig_img = px.bar(df_img, x="TimeStamp", y="Value", title="Images Created")
                    st.plotly_chart(fig_img, use_container_width=True)
                else: st.info("No image data.")

        with tab_cost:
            st.subheader("GenAI Hub Cost Summary Per Project")
            
            # --- DATA PREPARATION FOR PROJECT SUMMARY ---
            # 1. Agg Usage/Carbon per Project (Using 'Project' col)
            df_usage_agg = df_raw.groupby('Project').agg(
                Carbon_Total=('Carbon_g', 'sum'),
                Input_Tokens=('Value', lambda x: x[df_raw.loc[x.index, 'Metric'] == 'ProcessedPromptTokens'].sum()),
                Output_Tokens=('Value', lambda x: x[df_raw.loc[x.index, 'Metric'].isin(['GeneratedTokens', 'GeneratedCompletionTokens'])].sum())
            ).reset_index()
            
            # 2. Agg Cost per Project (ProjectName)
            df_cost_agg = pd.DataFrame()
            if not df_cost.empty:
                df_cost_agg = df_cost.groupby('ProjectName').agg(
                    Cost_SEK=('CostSEK', 'sum')
                ).reset_index()
            
            # 3. Merge Cost and Usage
            if not df_cost_agg.empty:
                df_project_summary = pd.merge(df_cost_agg, df_usage_agg, left_on='ProjectName', right_on='Project', how='outer')
                df_project_summary['ProjectName'] = df_project_summary['ProjectName'].fillna(df_project_summary['Project'])
                df_project_summary = df_project_summary.drop(columns=['Project']).fillna(0)
            else:
                df_project_summary = df_usage_agg.rename(columns={'Project': 'ProjectName'})
                df_project_summary['Cost_SEK'] = 0.0

            # --- TOP KPIs ---
            kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
            
            total_spend = df_project_summary['Cost_SEK'].sum()
            
            kpi_c1.metric("Average Monthly Cost", f"{total_spend:,.0f} SEK") 
            kpi_c2.metric("Total Cost (SEK)", f"{total_spend:,.0f}")
            kpi_c3.metric("Total Input Tokens", f"{df_project_summary['Input_Tokens'].sum()/1e6:.1f}M")
            kpi_c4.metric("Total Output Tokens", f"{df_project_summary['Output_Tokens'].sum()/1e6:.1f}M")
            
            st.markdown("---")

            # --- CHARTS ---
            c_chart, c_table = st.columns([1, 1])
            
            with c_chart:
                if not df_cost.empty:
                    # Stacked Bar Chart (Cost by Project over Time)
                    fig_trend = px.bar(
                        df_cost, 
                        x="Date", 
                        y="CostSEK", 
                        color="ProjectName",
                        title="Total Cost (SEK) by Month and Digital Product",
                        labels={"CostSEK": "Cost (SEK)", "Date": "Month"},
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    fig_trend.update_layout(hovermode="x unified")
                    st.plotly_chart(fig_trend, use_container_width=True)
                else:
                    st.info("No cost data to visualize trends.")

            with c_table:
                # Detailed Project Table
                st.markdown("#### Project Details")
                st.dataframe(
                    df_project_summary.sort_values("Cost_SEK", ascending=False),
                    column_config={
                        "ProjectName": "Digital Product / Project",
                        "Cost_SEK": st.column_config.NumberColumn("Consumption Cost", format="%.2f kr"),
                        "Carbon_Total": st.column_config.NumberColumn("CO₂ Footprint (g)", format="%.1f"),
                        "Input_Tokens": st.column_config.NumberColumn("Input Tokens", format="%.0f"),
                        "Output_Tokens": st.column_config.NumberColumn("Output Tokens", format="%.0f")
                    },
                    hide_index=True,
                    use_container_width=True
                )

        with tab_data:
            st.dataframe(df_raw.sort_values("TimeStamp", ascending=False), use_container_width=True)
            
    elif not show_debug:
        st.info("No data returned. Check Debug Logs or ensure your models have traffic.")