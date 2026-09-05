#!/usr/bin/env python3
"""
Crypto Market Data Fetcher

Fetches cryptocurrency market data from CoinGecko API and uploads to Supabase PostgreSQL.
Designed to run via GitLab CI on a schedule (twice daily).
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

# Load .env file for local development
from dotenv import load_dotenv
load_dotenv()

import requests
import psycopg2
from psycopg2.extras import execute_values

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration - Hardcoded fallbacks for CI/CD (variable substitution not working)
_api_key = os.environ.get('COINGECKO_API_KEY', '')
_db_url = os.environ.get('DATABASE_URL', '')
_retention_days_env = os.environ.get('RETENTION_DAYS', '90')

# GitLab CI / GitHub Actions fallbacks
COINGECKO_API_KEY = _api_key if _api_key and not _api_key.startswith('$') else 'CG-kzG3ytHELPMPU3GFcJD1UDx1'
DATABASE_URL = _db_url if _db_url and not _db_url.startswith('$') else 'postgresql://postgres:IntroProgramming%401@db.vnmsppcmnprubtyxyrsm.supabase.co:5432/postgres'

try:
    RETENTION_DAYS = int(_retention_days_env) if _retention_days_env and not _retention_days_env.startswith('$') else 90
except ValueError:
    RETENTION_DAYS = 90

# Debug: Log API key info (masked for security)
if COINGECKO_API_KEY:
    logger.info(f"API Key length: {len(COINGECKO_API_KEY)}, starts with: {COINGECKO_API_KEY[:5]}..., ends with: ...{COINGECKO_API_KEY[-4:]}")
else:
    logger.warning("No API key found!")

# CoinGecko API settings
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
COINS_PER_PAGE = 250
TOTAL_PAGES = 4  # 4 pages x 250 = 1000 coins
API_DELAY_SECONDS = 2.5  # Delay between API calls to respect rate limits


def fetch_market_data(page: int) -> Optional[list]:
    """
    Fetch market data from CoinGecko API for a specific page.
    
    Args:
        page: Page number (1-indexed)
        
    Returns:
        List of coin data or None if request fails
    """
    url = f"{COINGECKO_BASE_URL}/coins/markets"
    params = {
        'vs_currency': 'usd',
        'order': 'market_cap_desc',
        'per_page': COINS_PER_PAGE,
        'page': page,
        'price_change_percentage': '1h,24h,7d',
        'locale': 'en'
    }
    
    # Demo API uses header authentication (recommended by CoinGecko)
    headers = {'x-cg-demo-api-key': COINGECKO_API_KEY} if COINGECKO_API_KEY else {}
    
    for attempt in range(3):
        try:
            logger.info(f"Fetching page {page} (attempt {attempt + 1})")
            response = requests.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 429:
                # Rate limited - wait and retry
                wait_time = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
                
            response.raise_for_status()
            data = response.json()
            logger.info(f"Page {page}: Retrieved {len(data)} coins")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error on page {page}: {e}")
            if attempt < 2:
                time.sleep(5)
            continue
    
    return None


def calculate_adj_vol_rank(coins: list) -> list:
    """
    Calculate adjusted volume rank based on volume/market_cap ratio.
    
    Args:
        coins: List of coin data with volume and market cap
        
    Returns:
        Same list with adj_vol_rank added
    """
    # Calculate volume/market_cap ratio for each coin
    for coin in coins:
        market_cap = coin.get('market_cap') or 0
        volume = coin.get('total_volume') or 0
        
        if market_cap > 0:
            coin['_vol_ratio'] = volume / market_cap
        else:
            coin['_vol_ratio'] = 0
    
    # Sort by ratio descending and assign ranks
    sorted_coins = sorted(coins, key=lambda x: x['_vol_ratio'], reverse=True)
    for rank, coin in enumerate(sorted_coins, start=1):
        coin['adj_vol_rank'] = rank
    
    return coins


def transform_to_db_format(coins: list, timestamp: datetime) -> list:
    """
    Transform CoinGecko API data to database schema format.
    
    Args:
        coins: List of coin data from API
        timestamp: Timestamp for this data snapshot
        
    Returns:
        List of tuples ready for database insertion
    """
    records = []
    
    for coin in coins:
        record = (
            timestamp,                                              # as_of_ts
            coin.get('symbol', '').upper(),                        # symbol
            coin.get('current_price'),                             # price_usd
            coin.get('market_cap_rank'),                           # mkt_cap_rank
            coin.get('adj_vol_rank'),                              # adj_vol_rank
            coin.get('market_cap'),                                # market_cap_usd
            coin.get('total_volume'),                              # volume_24h_usd
            coin.get('price_change_percentage_1h_in_currency'),    # price_change_1h_pct
            coin.get('price_change_percentage_24h_in_currency'),   # price_change_24h_pct
            coin.get('price_change_percentage_7d_in_currency'),    # price_change_7d_pct
            coin.get('circulating_supply'),                        # circulating_supply
            coin.get('total_supply'),                              # total_supply
            'coingecko',                                           # source
            'api_markets'                                          # source_table
        )
        records.append(record)
    
    return records


def upload_to_database(records: list, dry_run: bool = False) -> bool:
    """
    Upload records to Supabase PostgreSQL database.
    
    Args:
        records: List of tuples to insert
        dry_run: If True, don't actually insert
        
    Returns:
        True if successful, False otherwise
    """
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable not set")
        return False
    
    if dry_run:
        logger.info(f"DRY RUN: Would insert {len(records)} records")
        return True
    
    conn = None
    try:
        logger.info(f"Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO crypto_market_history_all (
                as_of_ts, symbol, price_usd, mkt_cap_rank, adj_vol_rank,
                market_cap_usd, volume_24h_usd, price_change_1h_pct,
                price_change_24h_pct, price_change_7d_pct, circulating_supply,
                total_supply, source, source_table
            ) VALUES %s
        """
        
        logger.info(f"Inserting {len(records)} records...")
        execute_values(cursor, insert_query, records, page_size=100)
        
        conn.commit()
        cursor.close()
        
        logger.info(f"Successfully inserted {len(records)} records")
        return True
        
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()


def purge_old_records(retention_days: int = RETENTION_DAYS, dry_run: bool = False) -> bool:
    """
    Delete records older than retention_days to maintain a rolling window
    and prevent database storage limits from being exceeded.
    
    Args:
        retention_days: Number of days of historical snapshots to keep
        dry_run: If True, simulate deletion without executing
        
    Returns:
        True if successful, False otherwise
    """
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable not set")
        return False
    
    if retention_days <= 0:
        logger.info("Retention pruning disabled (retention_days <= 0)")
        return True
    
    if dry_run:
        logger.info(f"DRY RUN: Would purge records older than {retention_days} days")
        return True
    
    conn = None
    try:
        logger.info(f"Purging records older than {retention_days} days...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        purge_query = """
            DELETE FROM crypto_market_history_all
            WHERE as_of_ts < (NOW() - %s * INTERVAL '1 day')
        """
        cursor.execute(purge_query, (retention_days,))
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        
        logger.info(f"Successfully purged {deleted_count} records older than {retention_days} days")
        return True
        
    except psycopg2.Error as e:
        logger.error(f"Error purging old records: {e}")
        return False
    finally:
        if conn:
            conn.close()


def main():
    """Main execution function."""
    dry_run = '--dry-run' in sys.argv
    purge_only = '--purge-only' in sys.argv
    
    # Custom retention days if specified
    retention_days = RETENTION_DAYS
    for i, arg in enumerate(sys.argv):
        if arg == '--retention-days' and i + 1 < len(sys.argv):
            try:
                retention_days = int(sys.argv[i + 1])
            except ValueError:
                pass
    
    if dry_run:
        logger.info("Running in DRY RUN mode - no database changes will be made")
    
    if purge_only:
        logger.info(f"Running purge only (retention: {retention_days} days)")
        success = purge_old_records(retention_days=retention_days, dry_run=dry_run)
        sys.exit(0 if success else 1)
    
    # Timestamp for this run
    run_timestamp = datetime.now(timezone.utc)
    logger.info(f"Starting data fetch at {run_timestamp.isoformat()}")
    
    # Fetch all pages
    all_coins = []
    for page in range(1, TOTAL_PAGES + 1):
        data = fetch_market_data(page)
        
        if data is None:
            logger.error(f"Failed to fetch page {page}, aborting")
            sys.exit(1)
        
        all_coins.extend(data)
        
        # Delay between requests to respect rate limits
        if page < TOTAL_PAGES:
            time.sleep(API_DELAY_SECONDS)
    
    logger.info(f"Total coins fetched: {len(all_coins)}")
    
    # Calculate adjusted volume rank
    all_coins = calculate_adj_vol_rank(all_coins)
    
    # Transform to database format
    records = transform_to_db_format(all_coins, run_timestamp)
    
    # Upload to database
    success = upload_to_database(records, dry_run=dry_run)
    
    if success:
        logger.info("Data upload succeeded. Running retention cleanup...")
        purge_old_records(retention_days=retention_days, dry_run=dry_run)
        logger.info("Data sync completed successfully!")
        sys.exit(0)
    else:
        logger.error("Data sync failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
