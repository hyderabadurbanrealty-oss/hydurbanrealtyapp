"""
Scrape SRO transaction data for Alekhya Rise and update Supabase.

Usage:
    python scrape_alekhya_rise_sro.py
"""
import psycopg2
import json
import re
from datetime import datetime
from pathlib import Path

# Database connection string (Supabase PostgreSQL - using connection pooler)
DB_URL = "postgresql://postgres.qjgwnbszmojzgwmafvuc:LZGJwY0ryKkFKH5P@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

# Project name variations to search for
PROJECT_PATTERNS = [
    "alekhya rise",
    "alekhya",
    "alekya rise",
    "alekya"
]

def get_sro_data_for_project():
    """
    Query existing SRO transactions for Alekhya Rise from the database.
    Returns list of transactions.
    """
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    print("Searching for Alekhya Rise in SRO transactions...")
    
    # Build SQL query to search for any variation of the project name
    search_conditions = " OR ".join([
        f"LOWER(apartment) LIKE '%{pattern}%'" for pattern in PROJECT_PATTERNS
    ])
    
    query = f"""
        SELECT 
            id, sro_name, district, village, apartment, flat_no,
            reg_date, quarter, mkt_value, cons_value, price_per_sqft,
            scraped_at
        FROM sro_transactions
        WHERE {search_conditions}
        ORDER BY reg_date DESC
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    
    transactions = []
    for row in rows:
        transactions.append({
            'id': row[0],
            'sro_name': row[1],
            'district': row[2],
            'village': row[3],
            'apartment': row[4],
            'flat_no': row[5],
            'reg_date': row[6].strftime('%Y-%m-%d') if row[6] else None,
            'quarter': row[7],
            'mkt_value': float(row[8]) if row[8] else None,
            'cons_value': float(row[9]) if row[9] else None,
            'price_per_sqft': float(row[10]) if row[10] else None,
            'scraped_at': row[11].strftime('%Y-%m-%d %H:%M:%S') if row[11] else None
        })
    
    cur.close()
    conn.close()
    
    return transactions


def analyze_sro_data(transactions):
    """Analyze and summarize the SRO transaction data."""
    if not transactions:
        print("\n❌ No SRO transactions found for Alekhya Rise")
        return
    
    print(f"\n✅ Found {len(transactions)} SRO transactions for Alekhya Rise")
    print("=" * 80)
    
    # Group by quarter
    by_quarter = {}
    unique_flats = set()
    total_value = 0
    
    for t in transactions:
        quarter = t['quarter']
        if quarter not in by_quarter:
            by_quarter[quarter] = []
        by_quarter[quarter].append(t)
        
        if t['flat_no']:
            unique_flats.add(t['flat_no'])
        
        if t['mkt_value']:
            total_value += t['mkt_value']
    
    print(f"\nTotal Registered Units: {len(transactions)}")
    print(f"Unique Flats: {len(unique_flats)}")
    print(f"Total Market Value: ₹{total_value:,.0f}")
    
    if transactions and transactions[0]['price_per_sqft']:
        avg_price = sum(t['price_per_sqft'] for t in transactions if t['price_per_sqft']) / len([t for t in transactions if t['price_per_sqft']])
        print(f"Average Price per Sqft: ₹{avg_price:,.0f}")
    
    print("\n📊 Quarterly Breakdown:")
    print("-" * 80)
    for quarter in sorted(by_quarter.keys(), reverse=True):
        txs = by_quarter[quarter]
        q_flats = set(t['flat_no'] for t in txs if t['flat_no'])
        q_value = sum(t['mkt_value'] for t in txs if t['mkt_value'])
        print(f"{quarter}: {len(txs)} registrations, {len(q_flats)} unique flats, ₹{q_value:,.0f}")
    
    print("\n📋 Recent Transactions:")
    print("-" * 80)
    for i, t in enumerate(transactions[:10], 1):
        print(f"{i}. Flat: {t['flat_no'] or 'N/A'} | "
              f"Date: {t['reg_date'] or 'N/A'} | "
              f"Value: ₹{t['mkt_value']:,.0f if t['mkt_value'] else 'N/A'} | "
              f"Price/sqft: ₹{t['price_per_sqft']:,.0f if t['price_per_sqft'] else 'N/A'}")
    
    print("=" * 80)


def check_project_in_db():
    """Check if Alekhya Rise project exists in the projects table."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    print("\nChecking if Alekhya Rise exists in projects table...")
    
    search_conditions = " OR ".join([
        f"LOWER(project_name) LIKE '%{pattern}%'" for pattern in PROJECT_PATTERNS
    ])
    
    query = f"""
        SELECT id, project_name, project_status, district, locality, 
               total_flats, total_booked
        FROM projects
        WHERE {search_conditions}
    """
    
    cur.execute(query)
    project = cur.fetchone()
    
    if project:
        print(f"✅ Project found in database:")
        print(f"   ID: {project[0]}")
        print(f"   Name: {project[1]}")
        print(f"   Status: {project[2]}")
        print(f"   Location: {project[4]}, {project[3]}")
        print(f"   Total Flats: {project[5] or 'N/A'}")
        print(f"   Booked: {project[6] or 'N/A'}")
        return project[0]
    else:
        print("❌ Alekhya Rise not found in projects table")
        print("   You may need to scrape the RERA data first")
        return None
    
    cur.close()
    conn.close()


def main():
    print("=" * 80)
    print("SRO Data Analysis for Alekhya Rise")
    print("=" * 80)
    
    # Check if project exists in database
    project_id = check_project_in_db()
    
    # Get SRO transaction data
    transactions = get_sro_data_for_project()
    
    # Analyze the data
    analyze_sro_data(transactions)
    
    if transactions:
        # Save summary to file
        summary_file = Path(__file__).parent / "alekhya_rise_sro_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'project_id': project_id,
                'total_transactions': len(transactions),
                'unique_flats': len(set(t['flat_no'] for t in transactions if t['flat_no'])),
                'total_value': sum(t['mkt_value'] for t in transactions if t['mkt_value']),
                'avg_price_per_sqft': sum(t['price_per_sqft'] for t in transactions if t['price_per_sqft']) / len([t for t in transactions if t['price_per_sqft']]) if any(t['price_per_sqft'] for t in transactions) else None,
                'transactions': transactions
            }, f, indent=2, default=str)
        
        print(f"\n💾 Summary saved to: {summary_file}")
    
    print("\n" + "=" * 80)
    print("Note: This data is already in Supabase. To update with NEW data,")
    print("you would need to run the SRO scraper for the relevant SRO offices.")
    print("=" * 80)


if __name__ == "__main__":
    main()
