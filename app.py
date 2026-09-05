"""
Crypto Trend Tracker - Streamlit Dashboard

A web dashboard displaying top 1000 cryptocurrencies ranked by Volume/Market Cap ratio.
Features: Stablecoin exclusion, row selection, multi-coin comparison, snapshot history.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time

# Import database utilities
from utils.db import (
    get_snapshot_data,
    get_available_snapshots,
    get_summary_metrics,
    get_historical_data_multi,
    get_top_movers,
    get_all_symbols,
    filter_stablecoins,
    STABLECOIN_SYMBOLS
)

# Page configuration
st.set_page_config(
    page_title="Crypto Trend Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===== SESSION STATE INITIALIZATION =====
if 'selected_coins' not in st.session_state:
    st.session_state.selected_coins = []
if 'exclude_stablecoins' not in st.session_state:
    st.session_state.exclude_stablecoins = True
if 'reset_counter' not in st.session_state:
    st.session_state.reset_counter = 0

# Custom CSS for dark theme styling
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background: linear-gradient(180deg, #0d1117 0%, #161b22 100%);
    }
    
    /* Metric cards styling */
    [data-testid="metric-container"] {
        background: rgba(22, 27, 34, 0.8);
        border: 1px solid rgba(0, 212, 170, 0.2);
        border-radius: 12px;
        padding: 15px;
        backdrop-filter: blur(10px);
    }
    
    [data-testid="stMetricLabel"] {
        color: #8b949e !important;
    }
    
    [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 600;
    }
    
    [data-testid="stMetricDelta"] svg {
        display: none;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #ffffff !important;
    }
    
    /* Chip styling for selected coins */
    .coin-chip {
        display: inline-block;
        background: rgba(0, 212, 170, 0.2);
        border: 1px solid rgba(0, 212, 170, 0.5);
        border-radius: 16px;
        padding: 4px 12px;
        margin: 4px;
        color: #00d4aa;
        font-weight: 500;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


def format_large_number(num):
    """Format large numbers with K, M, B suffixes."""
    if num is None or pd.isna(num):
        return "N/A"
    if num >= 1e12:
        return f"${num/1e12:.2f}T"
    elif num >= 1e9:
        return f"${num/1e9:.2f}B"
    elif num >= 1e6:
        return f"${num/1e6:.2f}M"
    elif num >= 1e3:
        return f"${num/1e3:.2f}K"
    else:
        return f"${num:.2f}"


def format_snapshot_label(ts):
    """Format snapshot timestamp for display."""
    if ts == "Latest":
        return "Latest Data"
    try:
        dt = pd.to_datetime(ts)
        # Format: Feb 04, 2026 - 19:33 UTC
        return dt.strftime("%b %d, %Y - %H:%M UTC")
    except:
        return str(ts)


def add_coin_to_selection(symbol: str):
    """Add a coin to the selected coins list."""
    if symbol not in st.session_state.selected_coins:
        if len(st.session_state.selected_coins) >= 5:
            st.warning("⚠️ Max 5 coins selected. Remove one to add another.")
        else:
            st.session_state.selected_coins.append(symbol)


def remove_coin_from_selection(symbol: str):
    """Remove a coin from the selected coins list."""
    if symbol in st.session_state.selected_coins:
        st.session_state.selected_coins.remove(symbol)
        # Increment counter to force table re-render
        st.session_state.reset_counter += 1


def clear_all_selections():
    """Clear all selected coins."""
    st.session_state.selected_coins = []
    # Increment counter to force table re-render
    st.session_state.reset_counter += 1


def main():
    """Main dashboard application."""
    
    # ===== HEADER SECTION =====
    col_title, col_date = st.columns([3, 1])
    with col_title:
        st.markdown("# 📊 Crypto Trend Tracker")
    with col_date:
        st.markdown(f"### {datetime.now().strftime('%b %d, %Y')}")
    
    st.markdown("---")
    
    # ===== CONTROLS SECTION =====
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 2, 2])
    
    with ctrl_col1:
        # Feature 4: Snapshot selector (Increased limit and improved readability)
        available_snapshots = get_available_snapshots(limit=200)
        snapshot_options = ["Latest"] + [str(ts) for ts in available_snapshots]
        
        selected_snapshot_raw = st.selectbox(
            "📅 Snapshot",
            snapshot_options,
            index=0,
            format_func=format_snapshot_label,
            help="View data from a specific snapshot time"
        )
        snapshot_ts = None if selected_snapshot_raw == "Latest" else selected_snapshot_raw
    
    with ctrl_col2:
        # Feature 1: Stablecoin exclusion toggle
        st.session_state.exclude_stablecoins = st.toggle(
            "🚫 Exclude Stablecoins",
            value=st.session_state.exclude_stablecoins,
            help="Hide stablecoins (USDT, USDC, DAI, etc.) from trending view"
        )
    
    with ctrl_col3:
        # Show current snapshot info
        display_label = format_snapshot_label(selected_snapshot_raw)
        st.info(f"Showing: {display_label}")
    
    # ===== LOAD DATA =====
    try:
        with st.spinner("Loading market data..."):
            raw_df = get_snapshot_data(snapshot_ts)
            
            # Apply stablecoin filter
            if st.session_state.exclude_stablecoins:
                df = filter_stablecoins(raw_df, exclude=True)
            else:
                df = raw_df
            
            metrics = get_summary_metrics(df)
            gainers, losers = get_top_movers(df)
    except Exception as e:
        st.error(f"""
        ⚠️ **Database Connection Error**
        
        Unable to connect to the database. Please check your connection.
        
        *Technical details: {str(e)[:100]}...*
        """)
        st.stop()
    
    if df.empty:
        st.error("⚠️ No data available. Please ensure the data pipeline has run.")
        return
    
    # ===== SUMMARY METRICS =====
    st.markdown("### 📈 Market Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Coins Tracked",
            value=f"{metrics['total_coins']:,}"
        )
    
    with col2:
        st.metric(
            label="Avg Vol/MCap Ratio",
            value=f"{metrics['avg_ratio']:.4f}"
        )
    
    with col3:
        gainer_symbol, gainer_pct = metrics['top_gainer']
        st.metric(
            label="🚀 Top Gainer (24h)",
            value=gainer_symbol,
            delta=f"{gainer_pct:+.2f}%" if isinstance(gainer_pct, (int, float)) else None
        )
    
    with col4:
        active_symbol, active_ratio = metrics['most_active']
        st.metric(
            label="⚡ Most Active",
            value=active_symbol,
            delta=f"Ratio: {active_ratio:.4f}" if isinstance(active_ratio, (int, float)) else None
        )
    
    st.markdown("---")
    
    # ===== MAIN CONTENT: TABLE AND CHART =====
    col_table, col_chart = st.columns([3, 2])
    
    with col_table:
        st.markdown("### 🔥 Trending Coins")
        st.caption("💡 Select row to add to chart")
        
        # Prepare display dataframe
        display_df = df.copy()
        display_df['Rank'] = range(1, len(display_df) + 1)
        
        # Pre-calculate Select column based on session state
        # This ensures the table visual state matches the chips
        display_df['Select'] = display_df['symbol'].isin(st.session_state.selected_coins)
        
        display_df['Price'] = display_df['price_usd'].apply(
            lambda x: f"${x:,.4f}" if x < 1 else f"${x:,.2f}"
        )
        display_df['24h Change'] = display_df['price_change_24h_pct'].apply(
            lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A"
        )
        display_df['Market Cap'] = display_df['market_cap_usd'].apply(format_large_number)
        display_df['Volume (24h)'] = display_df['volume_24h_usd'].apply(format_large_number)
        display_df['Vol/MCap'] = display_df['vol_mcap_ratio'].apply(
            lambda x: f"{x:.4f}" if pd.notna(x) else "N/A"
        )
        
        # Select columns for display
        table_df = display_df[[
            'Select', 'Rank', 'symbol', 'Price', '24h Change', 
            'Market Cap', 'Volume (24h)', 'Vol/MCap'
        ]].rename(columns={'symbol': 'Symbol'})
        
        # Pagination
        col_pg1, col_pg2 = st.columns([1, 2])
        with col_pg1:
            page_size = st.selectbox("Rows", [25, 50, 100], index=0, key="page_size")
        
        total_pages = (len(table_df) - 1) // page_size + 1
        with col_pg2:
            page = st.number_input(
                f"Page (1-{total_pages})", 
                min_value=1, 
                max_value=total_pages, 
                value=1,
                key="page_num"
            )
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        # Feature 2: Selectable table using data_editor
        # Key includes reset_counter to force re-render when chips are removed
        edited_df = st.data_editor(
            table_df.iloc[start_idx:end_idx],
            use_container_width=True,
            hide_index=True,
            height=500,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "📌",
                    help="Select to add to comparison chart",
                    width="small"
                )
            },
            disabled=['Rank', 'Symbol', 'Price', '24h Change', 'Market Cap', 'Volume (24h)', 'Vol/MCap'],
            key=f"table_editor_{page}_{st.session_state.reset_counter}"
        )
        
        # Process selections from table
        # We check which rows are checked in the editor
        current_selected_in_table = edited_df[edited_df['Select'] == True]['Symbol'].tolist()
        
        # Logic: If a coin is checked in table but not in session state, add it.
        # If a coin is unchecked in table but IS in session state, remove it 
        # (BUT only if it was present on this page).
        
        page_symbols = table_df.iloc[start_idx:end_idx]['Symbol'].tolist()
        
        for symbol in current_selected_in_table:
             if symbol not in st.session_state.selected_coins:
                 # It was newly checked
                 add_coin_to_selection(symbol)
                 st.rerun()

        for symbol in page_symbols:
            if symbol not in current_selected_in_table and symbol in st.session_state.selected_coins:
                # It was newly unchecked
                remove_coin_from_selection(symbol)
                st.rerun()
    
    with col_chart:
        st.markdown("### 📉 Coin Comparison Chart")
        
        # Feature 2: Selected coins chips
        if st.session_state.selected_coins:
            st.markdown(f"**Selected Coins ({len(st.session_state.selected_coins)}/5):**")
            
            # Display chips with remove buttons
            cols = st.columns(6)
            for i, coin in enumerate(st.session_state.selected_coins):
                col_idx = i % 5
                with cols[col_idx]:
                    if st.button(f"❌ {coin}", key=f"rm_{coin}"):
                        remove_coin_from_selection(coin)
                        st.rerun()
            
            # Clear button
            with cols[5]:
                if st.button("🗑️ All", key="clear"):
                    clear_all_selections()
                    st.rerun()
        else:
            st.info("Select coins from the table to compare")
        
        # Feature 3: Metric selector
        metric_options = {
            "Vol/MCap Ratio": "vol_mcap_ratio",
            "Price (USD)": "price_usd",
            "24h Volume (USD)": "volume_24h_usd",
            "Market Cap (USD)": "market_cap_usd"
        }
        selected_metric = st.selectbox(
            "Metric",
            list(metric_options.keys()),
            index=0,
            key="metric_selector"
        )
        metric_col = metric_options[selected_metric]
        
        # Time range selector
        time_range = st.radio(
            "Time Range",
            ["7 Days", "14 Days", "30 Days", "90 Days"],
            horizontal=True,
            key="time_range"
        )
        days = int(time_range.split()[0])
        
        # Fetch and display historical data for selected coins
        coins_to_chart = st.session_state.selected_coins if st.session_state.selected_coins else ['BTC']
        hist_df = get_historical_data_multi(coins_to_chart, days)
        
        if not hist_df.empty and metric_col in hist_df.columns:
            fig = go.Figure()
            
            colors = ['#00d4aa', '#7c3aed', '#f59e0b', '#ef4444', '#3b82f6']
            
            for i, coin in enumerate(coins_to_chart):
                coin_data = hist_df[hist_df['symbol'] == coin]
                if not coin_data.empty:
                    fig.add_trace(go.Scatter(
                        x=coin_data['as_of_ts'],
                        y=coin_data[metric_col],
                        mode='lines',
                        name=coin,
                        line=dict(color=colors[i % len(colors)], width=2),
                        hovertemplate=f"<b>{coin}</b><br>" +
                                      f"{selected_metric}: %{{y:.4f}}<br>" +
                                      "Time: %{x}<extra></extra>"
                    ))
            
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=30, b=20),
                height=400,
                xaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.1)',
                    title=None
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(255,255,255,0.1)',
                    title=selected_metric
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="left",
                    x=0
                ),
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No historical data available for selected coins")
    
    # ===== TOP MOVERS SECTION =====
    st.markdown("---")
    st.markdown("### 🎯 Top Movers")
    
    col_gainers, col_losers = st.columns(2)
    
    with col_gainers:
        st.markdown("#### 🟢 Top Gainers")
        if not gainers.empty:
            for _, row in gainers.iterrows():
                pct = row['price_change_24h_pct']
                st.markdown(f"""
                <div style="background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3); 
                            border-radius: 8px; padding: 12px; margin: 8px 0;">
                    <span style="font-size: 1.2em; font-weight: 600; color: #ffffff;">{row['symbol']}</span>
                    <span style="float: right; color: #22c55e; font-weight: 600;">+{pct:.2f}%</span>
                </div>
                """, unsafe_allow_html=True)
    
    with col_losers:
        st.markdown("#### 🔴 Top Losers")
        if not losers.empty:
            for _, row in losers.iterrows():
                pct = row['price_change_24h_pct']
                st.markdown(f"""
                <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); 
                            border-radius: 8px; padding: 12px; margin: 8px 0;">
                    <span style="font-size: 1.2em; font-weight: 600; color: #ffffff;">{row['symbol']}</span>
                    <span style="float: right; color: #ef4444; font-weight: 600;">{pct:.2f}%</span>
                </div>
                """, unsafe_allow_html=True)
    
    # ===== FOOTER =====
    st.markdown("---")
    last_update = df['as_of_ts'].max() if 'as_of_ts' in df.columns else None
    
    st.caption(f"📅 Data snapshot: {last_update}")
    excluded_info = f"(Excluding {len(STABLECOIN_SYMBOLS)} stablecoins)" if st.session_state.exclude_stablecoins else ""
    st.caption(f"Data source: CoinGecko API | Built with Streamlit {excluded_info}")


if __name__ == "__main__":
    main()
