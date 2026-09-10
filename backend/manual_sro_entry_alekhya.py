"""
Manual SRO transaction data entry for Alekhya Rise.

Since the SRO portal scraping is not working, use this script to manually
enter SRO transaction data that you have collected from other sources.

Usage:
    1. Edit the ALEKHYA_TRANSACTIONS list below with your data
    2. Run: python manual_sro_entry_alekhya.py
"""
import psycopg2
from datetime import datetime

# Database connection string (Supabase PostgreSQL - using connection pooler)
DB_URL = "postgresql://postgres.qjgwnbszmojzgwmafvuc:LZGJwY0ryKkFKH5P@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

# Manual SRO transaction data for Alekhya Rise
# Add your transactions here in this format:
ALEKHYA_TRANSACTIONS = [
    # Example entry - replace with real data:
    {
        'sro_name': 'SERILINGAMPALLI',
        'district': 'RANGAREDDY',
        'village': 'NARSINGI',
        'apartment': 'ALEKHYA RISE',
        'flat_no': 'A-101',  # e.g., 'A-101', 'B-205', etc.
        'reg_date': '2024-06-15',  # Format: YYYY-MM-DD
        'quarter': '2024-Q2',  # Format: YYYY-Q1, YYYY-Q2, etc.
        'mkt_value': 5500000,  # Market value in rupees
        'cons_value': 5000000,  # Consideration value in rupees
        'price_per_sqft': 5500,  # Price per square foot
    },
    # Add more transactions below:
    # {
    #     'sro_name': 'SERILINGAMPALLI',
    #     'district': 'RANGAREDDY',
    #     'village': 'NARSINGI',
    #     'apartment': 'ALEKHYA RISE',
    #     'flat_no': 'A-102',
    #     'reg_date': '2024-07-20',
    #     'quarter': '2024-Q3',
    #     'mkt_value': 5600000,
    #     'cons_value': 5100000,
    #     'price_per_sqft': 5600,
    # },
]


def insert_transactions():
    """Insert manual SRO transactions into the database."""
    if not ALEKHYA_TRANSACTIONS:
        print("❌ No transactions to insert. Please add data to ALEKHYA_TRANSACTIONS list.")
        return
    
    # Remove example entry if it exists
    transactions = [t for t in ALEKHYA_TRANSACTIONS 
                   if not (t.get('flat_no') == 'A-101' and t.get('mkt_value') == 5500000)]
    
    if not transactions:
        print("❌ Only example data found. Please add real transaction data.")
        return
    
    print("=" * 80)
    print(f"Inserting {len(transactions)} SRO transactions for Alekhya Rise")
    print("=" * 80)
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        inserted = 0
        skipped = 0
        
        for t in transactions:
            try:
                # Convert date string to date object
                reg_date = datetime.strptime(t['reg_date'], '%Y-%m-%d').date() if t.get('reg_date') else None
                
                # Insert with ON CONFLICT DO NOTHING for idempotency
                cur.execute("""
                    INSERT INTO sro_transactions
                        (sro_name, district, village, apartment, flat_no,
                         reg_date, quarter, mkt_value, cons_value, price_per_sqft, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """, (
                    t.get('sro_name'),
                    t.get('district'),
                    t.get('village'),
                    t.get('apartment'),
                    t.get('flat_no'),
                    reg_date,
                    t.get('quarter'),
                    t.get('mkt_value'),
                    t.get('cons_value'),
                    t.get('price_per_sqft')
                ))
                
                if cur.fetchone():
                    inserted += 1
                    print(f"✅ Inserted: Flat {t.get('flat_no')} | Date: {t.get('reg_date')} | "
                          f"Value: ₹{t.get('mkt_value'):,}")
                else:
                    skipped += 1
                    print(f"⏭️  Skipped (duplicate): Flat {t.get('flat_no')}")
                    
            except Exception as e:
                print(f"❌ Error inserting transaction: {e}")
                print(f"   Data: {t}")
                conn.rollback()
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        
        print()
        print("=" * 80)
        print(f"✅ Completed: {inserted} inserted, {skipped} skipped")
        print("=" * 80)
        
        # Run analysis
        print("\nRunning analysis...")
        import subprocess
        subprocess.run(["python", "scrape_alekhya_rise_sro.py"], check=False)
        
    except Exception as e:
        print(f"❌ Database error: {e}")


def show_data_template():
    """Show a template for adding transaction data."""
    print()
    print("=" * 80)
    print("DATA ENTRY TEMPLATE")
    print("=" * 80)
    print("""
To add SRO transaction data, edit ALEKHYA_TRANSACTIONS in this file:

ALEKHYA_TRANSACTIONS = [
    {
        'sro_name': 'SERILINGAMPALLI',
        'district': 'RANGAREDDY',
        'village': 'NARSINGI',
        'apartment': 'ALEKHYA RISE',
        'flat_no': 'FLAT-NUMBER',     # e.g., 'A-101', 'B-205'
        'reg_date': 'YYYY-MM-DD',     # e.g., '2024-06-15'
        'quarter': 'YYYY-QN',         # e.g., '2024-Q2'
        'mkt_value': 5500000,         # Market value in ₹
        'cons_value': 5000000,        # Consideration value in ₹
        'price_per_sqft': 5500,       # Price per sqft in ₹
    },
    # Add more entries...
]

Quarter Reference:
  Q1 = Jan-Mar
  Q2 = Apr-Jun
  Q3 = Jul-Sep
  Q4 = Oct-Dec
""")
    print("=" * 80)


if __name__ == "__main__":
    print()
    print("┌" + "─" * 78 + "┐")
    print("│" + " " * 20 + "Manual SRO Data Entry - Alekhya Rise" + " " * 22 + "│")
    print("└" + "─" * 78 + "┘")
    print()
    
    if not ALEKHYA_TRANSACTIONS or len(ALEKHYA_TRANSACTIONS) == 1:
        print("ℹ️  No transaction data found in the script.")
        show_data_template()
    else:
        print(f"Found {len(ALEKHYA_TRANSACTIONS)} transaction(s) to insert.")
        print()
        response = input("Continue with insertion? (yes/no): ").strip().lower()
        if response == "yes":
            insert_transactions()
        else:
            print("Cancelled.")
