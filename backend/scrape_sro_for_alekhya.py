"""
Scrape SRO transactions for Alekhya Rise from SERILINGAMPALLI SRO office.

This script will:
1. Run the SRO scraper for SERILINGAMPALLI (covers Narsingi/Kokapet)
2. Filter transactions for "Alekhya Rise"
3. Update the Supabase database

Usage:
    python scrape_sro_for_alekhya.py [year] [test_mode]
    
Examples:
    python scrape_sro_for_alekhya.py 2024          # Scrape full year 2024
    python scrape_sro_for_alekhya.py 2024 test     # Test mode - only 100 docs
"""
import sys
import subprocess
from pathlib import Path

# SRO details for Serilingampalli (covers Narsingi/Kokapet area)
SRO_NAME = "SERILINGAMPALLI"
SRO_DIST_CODE = "15_1"
SRO_CODE = "1522"

def run_sro_scraper(year: str = "2024", test_mode: bool = False):
    """Run the SRO transaction scraper for Serilingampalli."""
    
    print("=" * 80)
    print(f"SRO Transaction Scraper for {SRO_NAME}")
    print("=" * 80)
    print(f"Year: {year}")
    print(f"Mode: {'TEST (100 docs)' if test_mode else 'FULL'}")
    print(f"Target: Alekhya Rise transactions")
    print("=" * 80)
    print()
    
    # Build command
    cmd = ["python", "sro_transaction_scraper.py"]
    
    if test_mode:
        cmd.extend(["test", SRO_NAME, year, "100"])
    else:
        cmd.extend(["full", SRO_NAME, year])
    
    print(f"Running command: {' '.join(cmd)}")
    print()
    
    # Run the scraper
    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent,
            capture_output=False,
            text=True,
            check=True
        )
        
        print()
        print("=" * 80)
        print("✅ SRO Scraper completed successfully!")
        print("=" * 80)
        print()
        
        # Now run the analysis script to see Alekhya Rise data
        print("Running analysis to check for Alekhya Rise transactions...")
        subprocess.run(
            ["python", "scrape_alekhya_rise_sro.py"],
            cwd=Path(__file__).parent,
            check=True
        )
        
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 80)
        print(f"❌ Error running SRO scraper: {e}")
        print("=" * 80)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ Unexpected error: {e}")
        print("=" * 80)
        sys.exit(1)


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else "2024"
    test_mode = len(sys.argv) > 2 and sys.argv[2].lower() == "test"
    
    print()
    print("┌" + "─" * 78 + "┐")
    print("│" + " " * 20 + "Alekhya Rise SRO Data Scraper" + " " * 29 + "│")
    print("└" + "─" * 78 + "┘")
    print()
    print("This will scrape SRO transaction data from SERILINGAMPALLI office")
    print("which covers the Narsingi/Kokapet area where Alekhya Rise is located.")
    print()
    
    if not test_mode:
        print("⚠️  WARNING: Running in FULL mode will scrape the entire year.")
        print("   This may take 30-60 minutes depending on the number of transactions.")
        print()
        response = input("Continue? (yes/no): ").strip().lower()
        if response != "yes":
            print("Cancelled.")
            sys.exit(0)
    
    run_sro_scraper(year, test_mode)


if __name__ == "__main__":
    main()