import streamlit as st
import requests
import pandas as pd
import numpy as np
import time
import json
import redis

@st.cache_resource
def get_redis_client():
    return redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

r = get_redis_client()
def get_watchdog_state():
    try:
        # Ask the Nginx gateway container for the watchdog state
        response = requests.get("http://gateway:80/watchdog/state", timeout=2)
        return response.json()
    except Exception as e:
        return {"banned": {}, "tracking": {}, "metrics": {}}

# ===================================
#   SESSION STATE 
# ===================================
if 'total_sent' not in st.session_state:
    st.session_state.total_sent = 0
if 'total_received' not in st.session_state:
    st.session_state.total_received = 0
if 'known_active_requests' not in st.session_state:
    st.session_state.known_active_requests = set()

# Fetch the live requests from Redis early so we can do the math
live_requests = r.hgetall("requests:payloads")
current_active_set = set(live_requests.keys())

# Calculate the differences since the last 2-second refresh
new_requests = current_active_set - st.session_state.known_active_requests
completed_requests = st.session_state.known_active_requests - current_active_set

# Increment the counters
st.session_state.total_sent += len(new_requests)
st.session_state.total_received += len(completed_requests)

# Save the current state for the NEXT loop
st.session_state.known_active_requests = current_active_set


# Page Configuration
st.set_page_config(page_title="Synapse Router Admin", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS
st.markdown("""
    <style>
    /* --- COMPRESSION FIXES --- */
    /* Remove the massive blank space at the top of the page */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }
    
    /* Hide the default Streamlit header completely */
    header {
        visibility: hidden !important;
    }
    
    /* Shrink the gaps above and below titles/subheaders */
    h1, h2, h3 {
        padding-top: 0rem !important;
        padding-bottom: 0.5rem !important;
    }

    /* --- STYLING FIXES --- */
    /* Metric purple numbers */
    div[data-testid="stMetricValue"] {
        color: #b185ff;
    }

   /* Dark Mode Cards for Metrics (Base State) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #0e1117; 
        border: 1px solid #2d333b; 
        border-radius: 12px;       
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); 
        min-height: 100%;
        
        /* Added !important to force the transition */
        transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease !important; 
    }
    
    /* The Hover State Animation */
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-5px) !important; /* Forces the lift */
        border-color: #b185ff !important;       /* Forces the purple border */
        box-shadow: 0 10px 20px rgba(177, 133, 255, 0.15) !important; /* Forces the glow */
    }
    
    /* Padding inside the metric boxes */
    div[data-testid="stMetric"] {
        padding: 5px;
    }
            
   /* --- NODE STATUS: SERVER RACK STYLE --- */
    .sr-rack-container {
        display: flex;
        flex-direction: column;
        
        /*Make the HTML act as the outer box! */
        background-color: #0e1117; 
        border: 1px solid #2d333b; 
        border-radius: 12px;       
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); 
        
        max-height: 250px; 
        overflow-y: auto;  
    }
    
    /* Custom sleek scrollbar for dark mode */
    .sr-rack-container::-webkit-scrollbar {
        width: 6px;
    }
    .sr-rack-container::-webkit-scrollbar-thumb {
        background-color: #2d333b;
        border-radius: 4px;
    }
    
    .sr-rack-slot {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-left: 4px solid #3fb950; /* Green bar on the left */
        padding: 12px 16px; /* Flushed padding */
        
        /* Removed the background color here so it inherits from the container! */
        border-bottom: 1px solid #1f242b;
    }
    .sr-rack-slot:last-child {
        border-bottom: none; 
    }
    .sr-rack-slot.banned-slot {
        border-left: 4px solid #f85149; /* Red bar on the left */
    }
    .sr-rack-name {
        font-family: monospace;
        color: #e6edf3;
        font-size: 15px;
    }
    .sr-badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-good { background: rgba(63, 185, 80, 0.1); color: #3fb950; border: 1px solid rgba(63, 185, 80, 0.3); }
    .badge-bad { background: rgba(248, 81, 73, 0.1); color: #f85149; border: 1px solid rgba(248, 81, 73, 0.3); }
    
    /* --- LIVE PAYLOAD FEED SCROLLBAR --- */
    div[data-testid="stCodeBlock"] {
        max-height: 200px; /* Locks the height to match the Failure Simulation box */
        overflow-y: auto;  /* Turns on the vertical scrollbar when text overflows */
    }

    /* Apply the custom dark scrollbar to the code block */
    div[data-testid="stCodeBlock"]::-webkit-scrollbar {
        width: 6px;
    }
    div[data-testid="stCodeBlock"]::-webkit-scrollbar-thumb {
        background-color: #2d333b;
        border-radius: 4px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Synapse Router | Admin Dashboard")
st.markdown("---")

# Fetch the real data from Watchdog
watchdog_data = get_watchdog_state()
metrics = watchdog_data.get("metrics", {})

# Calculate real-time stats
real_total_completed = metrics.get("total_requests_completed", 0)
total_latency = metrics.get("total_latency", 0)
uptime = metrics.get("uptime", 1)

# Averages
avg_latency = (total_latency / real_total_completed) if real_total_completed > 0 else 0
avg_throughput = real_total_completed / uptime

# ==========================================
# THE HIGH-LEVEL METRICS 
# ==========================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    with st.container(border=True):
        st.metric(label="Total Requests Sent", value=f"{st.session_state.total_sent:,}")

with col2:
    with st.container(border=True):
        # We can use the real completed count directly from Nginx!
        st.metric(label="Total Requests Completed", value=f"{real_total_completed:,}")

with col3:
    with st.container(border=True):
        st.metric(label="Average Throughput", value=f"{avg_throughput:.2f} req/s")

with col4:
    with st.container(border=True):
        st.metric(label="Average Latency", value=f"{avg_latency:.2f}s", delta_color="inverse")


# ==========================================
#  GRAPH & STATUS
# ==========================================
graph_col, status_col = st.columns([3, 1]) # 3-to-1 width ratio

with graph_col:
    st.subheader("GPU & CPU Utilization")
    # Mock data for the line chart (We will replace this with real data later)
    chart_data = pd.DataFrame(
        np.random.randn(20, 3) * 10 + 50,
        columns=['Worker 1 (GPU)', 'Worker 2 (GPU)', 'Worker 3 (GPU)']
    )
    st.line_chart(chart_data, height=250)

with status_col:
    st.subheader("Node Status")
    
    # We already fetched watchdog_data above
    banned_nodes = watchdog_data.get("banned", {})
    
    # Define our actual worker nodes
    all_nodes = ["worker-1", "worker-2", "worker-3"] ### made them static for now as we only made 3 worker containers
    
    # Build the HTML dynamically
    html_content = '<div class="sr-rack-container">'
    for node in all_nodes:
        if f"banned_{node}" in banned_nodes or node in banned_nodes:
            html_content += f'<div class="sr-rack-slot banned-slot"><span class="sr-rack-name">{node}</span><span class="sr-badge badge-bad">BANNED</span></div>'
        else:
            html_content += f'<div class="sr-rack-slot"><span class="sr-rack-name">{node}</span><span class="sr-badge badge-good">ACTIVE</span></div>'
    html_content += '</div>'

    # Render directly in the column, NO st.container()
    st.markdown(html_content, unsafe_allow_html=True)
#st.markdown("---")

# ==========================================
#  CONTROL & LIVE FEED
# ==========================================
control_col, feed_col = st.columns([1, 2])

with control_col:
    st.subheader("Failure Simulation")
    st.write("Force a node to crash to test the load balancer recovery.")
    
    # Enhancement: Dropdown instead of text input prevents user errors!
    target_node = st.selectbox("Select Node to Crash:", ["worker-1", "worker-2", "worker-3"])
    
    if st.button("⚠️ Simulate Crash", type="primary"):
        try:
            # The watchdog will then see this and execute the physical TCP kill!
            response = requests.post("http://gateway:80/watchdog/control", data={"ban_node": target_node})
            if response.status_code == 200:
                st.toast(f"Crash signal sent to {target_node}! Watchdog will sever connections.", icon="💥")
            else:
                st.error(f"Failed to send crash signal: {response.text}")
        except Exception as e:
            st.error(f"Error communicating with Gateway: {e}")
with feed_col:
    st.subheader("📡 Live Payload Feed")
    
    # Read the actual hash we created in Nginx's access.lua
    live_requests = r.hgetall("requests:payloads")
    
    feed_text = ""
    if not live_requests:
        feed_text = "> Waiting for incoming traffic...\n> Redis 'requests:payloads' is currently empty."
    else:
        # Loop through whatever is sitting in Redis right now
        for req_id, payload in live_requests.items():
            # Get the assigned node from the tracking list if it exists
            watchdog_data = get_watchdog_state()
            assigned_node = watchdog_data.get("tracking", {}).get(f"tracking_{req_id}", "Assigning...")
            
            feed_text += f"[{time.strftime('%H:%M:%S')}] {req_id} -> {assigned_node}\n"

    # Render it inside the code block
    feed_placeholder = st.empty()
    with feed_placeholder.container():
        st.code(feed_text, language="bash")


# ==========================================
# AUTO REFRESH LOOP
# ==========================================
time.sleep(1)  # Wait 2 seconds
st.rerun()     # Tell Streamlit to automatically reload the page with fresh data!