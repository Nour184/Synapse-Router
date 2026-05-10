import streamlit as st
import requests
import pandas as pd
import numpy as np
import time


# 1. Page Configuration (Must be the first Streamlit command)
# This forces the dashboard to use the full width of the screen and sets a dark theme vibe
st.set_page_config(page_title="Synapse Router Admin", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS to inject some of that purple aesthetic from your reference image
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
        gap: 12px;
        padding-top: 5px;
        max-height: 200px; /* Forces the box to stop growing and scroll instead */
        overflow-y: auto;  /* Turns on the vertical scrollbar */
        padding-right: 5px; /* Gives the scrollbar room to breathe */
        margin-bottom: -10px;
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
        padding: 8px 12px;
        background: #0e1117;
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
    </style>
""", unsafe_allow_html=True)

st.title("Synapse Router | Admin Dashboard")
st.markdown("---")

# ==========================================
# ROW 1: THE HIGH-LEVEL METRICS (KPIs)
# ==========================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    with st.container(border=True):
        st.metric(label="Total Requests Sent", value="1,245")

with col2:
    with st.container(border=True):
        st.metric(label="Total Requests Received", value="1,240")

with col3:
    with st.container(border=True):
        st.metric(label="Average Throughput", value="45 req/sec")

with col4:
    with st.container(border=True):
        st.metric(label="Average Latency", value="1.2s", delta_color="inverse")



# ==========================================
# ROW 2: GRAPH & STATUS
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
    with st.container(border=True):
        st.markdown("""
        <div class="sr-rack-container">
            <div class="sr-rack-slot">
                <span class="sr-rack-name">node-01</span>
                <span class="sr-badge badge-good">ACTIVE</span>
            </div>
            <div class="sr-rack-slot banned-slot">
                <span class="sr-rack-name">node-02</span>
                <span class="sr-badge badge-bad">TIMEOUT</span>
            </div>
            <div class="sr-rack-slot">
                <span class="sr-rack-name">node-03</span>
                <span class="sr-badge badge-good">ACTIVE</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
#st.markdown("---")

# ==========================================
# ROW 3: CONTROL & LIVE FEED
# ==========================================
control_col, feed_col = st.columns([1, 2])

with control_col:
    st.subheader("Failure Simulation")
    st.write("Force a node to crash to test the load balancer recovery.")
    
    # Enhancement: Dropdown instead of text input prevents user errors!
    target_node = st.selectbox("Select Node to Crash:", ["local-worker-1", "local-worker-2", "local-worker-3"])
    
    if st.button("⚠️ Simulate Crash", type="primary"):
        st.toast(f"Crash signal sent to {target_node}!", icon="💥")
        # Later: We will add the requests.post() here to hit Nginx

with feed_col:
    st.subheader("Live Payload Feed")
    # Mock live feed area
    feed_placeholder = st.empty()
    with feed_placeholder.container():
        st.code("""
[2026-05-10 17:15:22] req-1777645486-8147 -> Routed to Node 1
[2026-05-10 17:15:23] req-1777645491-6310 -> Routed to Node 3
[2026-05-10 17:15:25] req-1777645487-7289 -> Processing...
        """, language="bash")