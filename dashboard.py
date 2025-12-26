"""
Insta Outreach Command Center - Streamlit Dashboard
Hosted version for Streamlit Cloud
"""
import streamlit as st
import pandas as pd
import oracledb
from pandas.core.series import Series

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Insta Outreach Command Center", page_icon="assets/logo.ico")

# --- Custom CSS ---
st.markdown("""
<style>
    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 5rem;
        padding-right: 5rem;
    }
    /* Title */
    h1 {
        font-size: 2.5rem;
        font-weight: 700;
    }
    /* Headers */
    h2 {
        font-size: 2rem;
        font-weight: 600;
    }
    /* Subheaders */
    h3 {
        font-size: 1.5rem;
        font-weight: 500;
    }
    /* KPI Metrics */
    .stMetric {
        border: 1px solid #262730;
        border-radius: 0.5rem;
        padding: 1rem;
        background-color: #0E1117;
    }
    /* Dataframes */
    .stDataFrame {
        border: 1px solid #262730;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Database Connection using Streamlit Secrets ---
@st.cache_resource
def get_connection_pool():
    """Creates a connection pool using Streamlit secrets."""
    try:
        pool = oracledb.create_pool(
            user=st.secrets["oracle"]["user"],
            password=st.secrets["oracle"]["password"],
            dsn=st.secrets["oracle"]["dsn"],
            config_dir=None,  # Use wallet from secrets if needed
            min=1,
            max=5,
            increment=1
        )
        return pool
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        return None

def get_connection():
    """Acquires a connection from the pool."""
    pool = get_connection_pool()
    if pool:
        return pool.acquire()
    return None

@st.cache_data(ttl=300)
def load_activity_data():
    """Fetches the full activity log from the database."""
    sql = """
        SELECT
            l.CREATED_AT,
            a.OWNER_OPERATOR,
            l.ACTOR_USERNAME,
            l.TARGET_USERNAME,
            p.STATUS,
            l.MESSAGE_TEXT
        FROM OUTREACH_LOGS l
        JOIN ACTORS a ON l.ACTOR_USERNAME = a.USERNAME
        LEFT JOIN PROSPECTS p ON l.TARGET_USERNAME = p.TARGET_USERNAME
        ORDER BY l.CREATED_AT DESC
    """
    conn = get_connection()
    if not conn:
        return pd.DataFrame()

    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            df = pd.DataFrame.from_records(rows, columns=columns)

            if not df.empty and 'CREATED_AT' in df.columns:
                df['CREATED_AT'] = pd.to_datetime(df['CREATED_AT'])
                s = df['CREATED_AT']
                if s.dt.tz is None:
                    s = s.dt.tz_localize('UTC')
                df['CREATED_AT'] = s.dt.tz_convert('Asia/Karachi')
                df = df.rename(columns={'CREATED_AT': 'Time (GMT+5)'})
            return df
    finally:
        conn.close()

@st.cache_data(ttl=300)
def load_prospects_data():
    """Fetches the raw prospects table for the CRM view."""
    sql = "SELECT * FROM PROSPECTS ORDER BY FIRST_CONTACTED DESC"
    conn = get_connection()
    if not conn:
        return pd.DataFrame()

    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame.from_records(rows, columns=columns)
    finally:
        conn.close()

# --- Main App UI ---

# --- Header with Sync Button ---
col1, col2 = st.columns([0.85, 0.15])
with col1:
    st.title("Insta Outreach Command Center")
with col2:
    st.write("")
    st.write("")
    if st.button("Sync Data", help="Reloads all data from the database."):
        st.cache_data.clear()
        st.rerun()

# --- Data Loading and Processing ---
cached_df = load_activity_data()

if cached_df.empty:
    st.warning("No outreach activity data found. The database might be empty or connection failed.")
else:
    df = cached_df.copy()

    # --- UI Tabs ---
    tab1, tab2, tab3 = st.tabs(["Performance Dashboard", "Lead Management (CRM)", "Message Log"])

    time_series = None
    if 'Time (GMT+5)' in df.columns:
        df['Time (GMT+5)'] = pd.to_datetime(df['Time (GMT+5)'])
        time_series: Series = df['Time (GMT+5)']

    with tab1:
        st.header("Performance Overview")

        # --- Controls ---
        with st.container():
            st.subheader("Filters")
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
                    ["All Time", "Today", "This Week", "This Month"],
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

        # --- KPIs ---
        with st.container():
            st.subheader("High-Level KPIs")
            kpi_cols = st.columns(3)
            total_dms = len(filtered_df)
            unique_prospects = filtered_df['TARGET_USERNAME'].nunique()

            total_active_days = 0
            if time_series is not None and not filtered_df.empty:
                total_active_days = filtered_df['Time (GMT+5)'].dt.date.nunique()

            avg_dms_per_day = total_dms / total_active_days if total_active_days > 0 else 0

            kpi_cols[0].metric("Total DMs Sent", f"{total_dms:,}")
            kpi_cols[1].metric("Unique Prospects Contacted", f"{unique_prospects:,}")

            if date_filter != "Today":
                kpi_cols[2].metric("Avg. DMs Per Day", f"{avg_dms_per_day:.1f}")
            else:
                kpi_cols[2].metric("Avg. DMs Per Day", "-")

        st.divider()

        # --- Charts ---
        with st.container():
            chart_cols = st.columns(2)
            with chart_cols[0]:
                st.subheader("Leaderboard")
                if not filtered_df.empty:
                    leaderboard = filtered_df[grouping_col].value_counts().reset_index()
                    leaderboard.columns = [grouping_col, 'Messages Sent']
                    st.dataframe(leaderboard, use_container_width=True)
                else:
                    st.write("No data for this period.")

            with chart_cols[1]:
                st.subheader("Performance Over Time")
                if not filtered_df.empty:
                    dms_per_day = filtered_df.set_index('Time (GMT+5)').resample('D').size()
                    st.line_chart(dms_per_day)
                else:
                    st.write("No data for this period.")

        # --- Daily Matrix ---
        with st.container():
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

                if pivot_table.empty:
                    st.info("No outreach data available for the selected filters.")
                else:
                    try:
                        st.dataframe(
                            pivot_table.style.background_gradient(cmap="Greens", axis=None).format("{:.0f}"),
                            use_container_width=True
                        )
                    except Exception as e:
                        # Fallback if styling fails (e.g., missing dependencies)
                        st.warning(f"Could not render styled table: {e}")
                        st.dataframe(pivot_table, use_container_width=True)
            else:
                st.write("No data for this period.")

    # =========================================================================
    # TAB 2: LEAD MANAGEMENT (CRM)
    # =========================================================================
    with tab2:
        st.header("Lead Management CRM")
        prospects_df = load_prospects_data()
        if not prospects_df.empty:
            st.dataframe(prospects_df, use_container_width=True)
        else:
            st.write("No prospects data found.")

    # =========================================================================
    # TAB 3: MESSAGE LOG
    # =========================================================================
    with tab3:
        st.header("Raw Message Log")
        column_order = ["Time (GMT+5)", "OWNER_OPERATOR", "ACTOR_USERNAME", "TARGET_USERNAME", "MESSAGE_TEXT", "STATUS"]
        display_cols = [col for col in column_order if col in df.columns]
        st.dataframe(df[display_cols], use_container_width=True)
f.empty:
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

            if pivot_table.empty:
                st.info("No outreach data available for the selected filters.")
            else:
                try:
                    st.dataframe(
                        pivot_table.style.background_gradient(cmap="Greens", axis=None).format("{:.0f}"),
                        use_container_width=True
                    )
                except Exception as e:
                    # Fallback if styling fails (e.g., missing dependencies)
                    st.warning(f"Could not render styled table: {e}")
                    st.dataframe(pivot_table, use_container_width=True)
        else:
            st.write("No data for this period.")

    # =========================================================================
    # TAB 2: LEAD MANAGEMENT (CRM)
    # =========================================================================
    with tab2:
        st.header("Lead Management CRM")
        prospects_df = load_prospects_data()
        if not prospects_df.empty:
            st.dataframe(prospects_df, use_container_width=True)
        else:
            st.write("No prospects data found.")

    # =========================================================================
    # TAB 3: MESSAGE LOG
    # =========================================================================
    with tab3:
        st.header("Raw Message Log")
        column_order = ["Time (GMT+5)", "OWNER_OPERATOR", "ACTOR_USERNAME", "TARGET_USERNAME", "MESSAGE_TEXT", "STATUS"]
        display_cols = [col for col in column_order if col in df.columns]
        st.dataframe(df[display_cols], use_container_width=True)
