"""
Database utilities for connecting to Supabase PostgreSQL.
Enhanced with stablecoin filtering, snapshot selection, and multi-coin historical data.
"""

import os
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase API Credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== STABLECOIN LIST =====
# Common stablecoins to exclude from trending analysis
STABLECOIN_SYMBOLS = {
    'USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'FDUSD', 'USDP', 'GUSD',
    'FRAX', 'LUSD', 'SUSD', 'USDD', 'PYUSD', 'CUSD', 'EURC', 'EURT',
    'UST', 'MIM', 'USDJ', 'USTC', 'HUSD', 'TRIBE', 'FEI', 'ALUSD',
    'USD+', 'EURS', 'XSGD', 'BIDR', 'IDRT', 'BRZ', 'GYEN', 'ZUSD',
    'OUSD', 'DOLA', 'HAY', 'CRVUSD', 'GHO', 'USDB', 'UXD', 'USDX',
    'GYD', 'USDY', 'USDZ', 'EUROe', 'agEUR', 'CEUR'
}


def filter_stablecoins(df: pd.DataFrame, exclude: bool = True) -> pd.DataFrame:
    """
    Filter stablecoins from the dataframe.
    
    Args:
        df: DataFrame with crypto data containing 'symbol' column.
        exclude: If True, remove stablecoins. If False, return only stablecoins.
    
    Returns:
        Filtered DataFrame.
    """
    if df.empty or 'symbol' not in df.columns:
        return df
    
    mask = df['symbol'].isin(STABLECOIN_SYMBOLS)
    return df[~mask] if exclude else df[mask]


def get_available_snapshots(limit: int = 50) -> list:
    """
    Get list of available snapshot timestamps.
    
    Returns:
        List of unique as_of_ts values, most recent first.
    """
    response = supabase.table("crypto_market_history_all") \
        .select("as_of_ts") \
        .order("as_of_ts", desc=True) \
        .limit(limit * 1000) \
        .execute()
    
    if not response.data:
        return []
    
    # Get unique timestamps
    timestamps = list(set(row["as_of_ts"] for row in response.data))
    timestamps.sort(reverse=True)
    return timestamps[:limit]


def get_snapshot_data(snapshot_ts: str = None) -> pd.DataFrame:
    """
    Fetch crypto data for a specific snapshot timestamp.
    
    Args:
        snapshot_ts: Specific timestamp to fetch. If None, uses latest.
    
    Returns:
        DataFrame with snapshot data.
    """
    # If no specific timestamp, get the latest
    if snapshot_ts is None:
        response = supabase.table("crypto_market_history_all") \
            .select("as_of_ts") \
            .order("as_of_ts", desc=True) \
            .limit(1) \
            .execute()
        
        if not response.data:
            return pd.DataFrame()
        
        snapshot_ts = response.data[0]["as_of_ts"]
    
    # Fetch all records for that timestamp
    response = supabase.table("crypto_market_history_all") \
        .select("*") \
        .eq("as_of_ts", snapshot_ts) \
        .order("adj_vol_rank", desc=False) \
        .limit(1000) \
        .execute()
    
    df = pd.DataFrame(response.data)
    
    if not df.empty:
        # Calculate Vol/MCap ratio locally
        df['vol_mcap_ratio'] = df.apply(
            lambda x: (x['volume_24h_usd'] / x['market_cap_usd']) if x['market_cap_usd'] > 0 else 0, 
            axis=1
        )
    
    return df


def get_latest_snapshot() -> pd.DataFrame:
    """Fetch the most recent snapshot (wrapper for backwards compatibility)."""
    return get_snapshot_data(snapshot_ts=None)


def get_summary_metrics(df: pd.DataFrame) -> dict:
    """
    Calculate summary metrics from the snapshot.
    """
    if df.empty:
        return {
            'total_coins': 0,
            'avg_ratio': 0,
            'top_gainer': ('N/A', 0),
            'most_active': ('N/A', 0)
        }
    
    # Filter out NaN for metrics calculation
    valid_df = df.dropna(subset=['price_change_24h_pct', 'vol_mcap_ratio'])
    
    if valid_df.empty:
        return {
            'total_coins': len(df),
            'avg_ratio': df['vol_mcap_ratio'].mean() if 'vol_mcap_ratio' in df else 0,
            'top_gainer': ('N/A', 0),
            'most_active': ('N/A', 0)
        }
    
    # Top gainer by 24h price change
    top_gainer_idx = valid_df['price_change_24h_pct'].idxmax()
    top_gainer = (
        valid_df.loc[top_gainer_idx, 'symbol'],
        valid_df.loc[top_gainer_idx, 'price_change_24h_pct']
    )
    
    # Most active by vol/mcap ratio
    most_active_idx = valid_df['vol_mcap_ratio'].idxmax()
    most_active = (
        valid_df.loc[most_active_idx, 'symbol'],
        valid_df.loc[most_active_idx, 'vol_mcap_ratio']
    )
    
    return {
        'total_coins': len(df),
        'avg_ratio': df['vol_mcap_ratio'].mean(),
        'top_gainer': top_gainer,
        'most_active': most_active
    }


def get_historical_data_multi(symbols: list, days: int = 7) -> pd.DataFrame:
    """
    Fetch historical data for multiple coins.
    
    Args:
        symbols: List of coin symbols (e.g., ['BTC', 'ETH']).
        days: Number of days to look back.
    
    Returns:
        Combined DataFrame with 'symbol' column for grouping.
    """
    if not symbols:
        return pd.DataFrame()
    
    all_data = []
    
    for symbol in symbols:
        response = supabase.table("crypto_market_history_all") \
            .select("as_of_ts, symbol, price_usd, volume_24h_usd, market_cap_usd, price_change_24h_pct") \
            .eq("symbol", symbol.upper()) \
            .order("as_of_ts", desc=False) \
            .limit(100) \
            .execute()
        
        if response.data:
            all_data.extend(response.data)
    
    if not all_data:
        return pd.DataFrame()
    
    df = pd.DataFrame(all_data)
    
    # Calculate Vol/MCap ratio
    df['vol_mcap_ratio'] = df.apply(
        lambda x: (x['volume_24h_usd'] / x['market_cap_usd']) if x['market_cap_usd'] > 0 else 0, 
        axis=1
    )
    
    # Filter for days
    df['as_of_ts'] = pd.to_datetime(df['as_of_ts'])
    cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=days)
    df = df[df['as_of_ts'] >= cutoff]
    
    return df


def get_historical_data(symbol: str, days: int = 7) -> pd.DataFrame:
    """Fetch historical data for a single coin (wrapper for backwards compatibility)."""
    return get_historical_data_multi([symbol], days)


def get_top_movers(df: pd.DataFrame, n: int = 2) -> tuple:
    """
    Get top gainers and losers from the snapshot.
    
    Args:
        df: DataFrame with latest crypto data.
        n: Number of top movers to return.
        
    Returns:
        Tuple of (gainers_df, losers_df).
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # Filter out NaN values for price change
    movers_df = df.dropna(subset=['price_change_24h_pct'])
    
    if movers_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    sorted_df = movers_df.sort_values('price_change_24h_pct', ascending=False)
    gainers = sorted_df.head(n)[['symbol', 'price_usd', 'price_change_24h_pct']]
    losers = sorted_df.tail(n)[['symbol', 'price_usd', 'price_change_24h_pct']]
    
    return gainers, losers


def get_all_symbols(df: pd.DataFrame) -> list:
    """Get list of all unique symbols from the snapshot."""
    if df.empty:
        return []
    return sorted(df['symbol'].unique().tolist())
