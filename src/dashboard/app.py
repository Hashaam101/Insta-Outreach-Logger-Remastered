import sys
import os
import streamlit as st
import pandas as pd
import numpy as np
from pandas.core.series import Series

# This is a crucial step to ensure the script can find the 'src.core' module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.database import DatabaseManager

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Insta Outreach Command Center")

# --- Database Connection & Caching ---
@st.cache_resource
def get_db_manager():
    return DatabaseManager()

@st.cache_data(ttl=300)
def load_activity_data():
    """Fetches the full activity log from the database."""
    df = get_db_manager().get_full_activity_log()
    if not df.empty and 'CREATED_AT' in df.columns:
        s = pd.to_datetime(df['CREATED_AT'])
        if s.dt.tz is None:
            s = s.dt.tz_localize('UTC')
        df['CREATED_AT'] = s.dt.tz_convert('Asia/Karachi')
        df = df.rename(columns={'CREATED_AT': 'Time (GMT+5)'})
    return df

@st.cache_data(ttl=300)
def load_prospects_data():
    """Fetches the raw prospects table for the CRM view."""
    return get_db_manager().get_all_prospects_df()

# --- Main App UI ---

# --- Header with Sync Button ---
col1, col2 = st.columns([0.85, 0.15])
with col1:
    st.title("📊 Insta Outreach Command Center")
with col2:
    st.write("") # Spacer
    st.write("") # Spacer
    if st.button("🔄 Sync Data", help="Reloads all data from the database."):
        st.cache_data.clear()
        st.rerun()

# --- Data Loading and Processing ---
cached_df = load_activity_data()

if cached_df.empty:
    st.warning("No outreach activity data found. The database might be empty.")
else:
    df = cached_df.copy()

    # --- UI Tabs ---
    tab1, tab2, tab3 = st.tabs(["📈 Performance Dashboard", "🕵️ Lead Management (CRM)", "✉️ Message Log"])
    
    time_series = None
    if 'Time (GMT+5)' in df.columns:
        df['Time (GMT+5)'] = pd.to_datetime(df['Time (GMT+5)'])
        time_series: Series = df['Time (GMT+5)']

    with tab1:
        st.header("Performance Overview")

        # --- Moved Controls ---
        control_cols = st.columns(2)
        with control_cols[0]:
            view_mode = st.radio(
                "Group Analytics By",
                ["Operator", "Actor"],
                key="view_mode",
                horizontal=True,
                help="Changes the grouping for all charts on this page."
            )
        with control_cols[1]:
            date_filter = st.radio(
                "Filter by Date",
                ["All Time", "Today", "This Week", "This Month"], # Reordered options
                horizontal=True,
                key="date_filter"
            )
        
        grouping_col = 'OWNER_OPERATOR' if view_mode == "Operator" else 'ACTOR_USERNAME'
        
        # --- Filter Data Based on Selection ---
        filtered_df = df
        now = pd.Timestamp.now(tz='Asia/Karachi')
        if date_filter == "Today":
            start_date = now.normalize()
            filtered_df = df[df['Time (GMT+5)'] >= start_date]
        elif date_filter == "This Week":
            start_date = now - pd.to_timedelta(now.dayofweek, unit='d')
            start_date = start_date.normalize()
            filtered_df = df[df['Time (GMT+5)'] >= start_date]
        elif date_filter == "This Month":
            start_date = now.replace(day=1).normalize()
            filtered_df = df[df['Time (GMT+5)'] >= start_date]

        
        st.divider()

        # --- KPIs (use filtered_df) ---
        st.subheader("High-Level KPIs")
        kpi_cols = st.columns(3)
        total_dms = len(filtered_df)
        unique_prospects = filtered_df['TARGET_USERNAME'].nunique()
        
        total_active_days = 0
        if time_series is not None and not filtered_df.empty:
            # Recalculate active days on the filtered series
            total_active_days = filtered_df['Time (GMT+5)'].dt.date.nunique()
        
        avg_dms_per_day = total_dms / total_active_days if total_active_days > 0 else 0

        kpi_cols[0].metric("Total DMs Sent", f"{total_dms:,}")
        kpi_cols[1].metric("Unique Prospects Contacted", f"{unique_prospects:,}")
        
        if date_filter != "Today": # Conditionally display
            kpi_cols[2].metric("Avg. DMs Per Day", f"{avg_dms_per_day:.1f}")
        else:
            kpi_cols[2].metric("Avg. DMs Per Day", "-") # Display a dash for "Today"
        
        st.divider()

        # --- Charts (use filtered_df) ---
        chart_cols = st.columns(2)
        with chart_cols[0]:
            st.subheader("Leaderboard")
            if not filtered_df.empty:
                leaderboard = filtered_df[grouping_col].value_counts().reset_index()
                leaderboard.columns = [grouping_col, 'Messages Sent']
                st.dataframe(leaderboard, width='stretch')
            else:
                st.write("No data for this period.")

        with chart_cols[1]:
            st.subheader("Performance Over Time")
            if not filtered_df.empty:
                dms_per_day = filtered_df.set_index('Time (GMT+5)').resample('D').size()
                st.line_chart(dms_per_day)
            else:
                st.write("No data for this period.")

        # --- Daily Matrix (use filtered_df) ---
        st.subheader("Daily Activity Heatmap")
        if not filtered_df.empty:
            filtered_df['Date'] = filtered_df['Time (GMT+5)'].dt.date
            
            pivot_table = pd.pivot_table(
                filtered_df,
                index='Date',
                columns=grouping_col,
                values='TARGET_USERNAME',
                aggfunc='count',
                fill_value=0
            )
            pivot_table.columns.name = None
            pivot_table = pivot_table.sort_index(ascending=False)

            st.dataframe(
                pivot_table.style.background_gradient(cmap="Greens", axis=None).format("{:.0f}"),
                width='stretch'
            )
        else:
            st.write("No data for this period.")



    # =========================================================================
    # TAB 2: LEAD MANAGEMENT (CRM)
    # =========================================================================
    with tab2:
        st.header("Lead Management CRM")
        prospects_df = load_prospects_data()
        if not prospects_df.empty:
            edited_df = st.data_editor(prospects_df, key="prospects_editor", num_rows="dynamic", disabled=['TARGET_USERNAME', 'OWNER_ACTOR', 'FIRST_CONTACTED'], width='stretch')
            if st.button("Save Prospect Changes"):
                diff = prospects_df.compare(edited_df)
                if not diff.empty:
                    pass

    # =========================================================================
    # TAB 3: MESSAGE LOG
    # =========================================================================
    with tab3:
        st.header("Raw Message Log")
        column_order = ["Time (GMT+5)", "OWNER_OPERATOR", "ACTOR_USERNAME", "TARGET_USERNAME", "MESSAGE_TEXT", "STATUS"]
        display_cols = [col for col in column_order if col in df.columns]
        st.dataframe(df[display_cols], width='stretch')
