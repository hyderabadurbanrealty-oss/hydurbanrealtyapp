"""
Scrape RERA data for Alekhya Rise and update Supabase.

Usage:
    python scrape_alekhya_rera.py
"""
import subprocess
import sys
from pathlib import Path

PROJECT_NAME = "ALEKHYA RISE"

def main():
    print("=" * 80)
    print(f"RERA Data Scraper for {PROJECT_NAME}")
    print("=" * 80)
    print()
    
    print(f"This will scrape detailed RERA information for {PROJECT_NAME}")
    print("and update the Supabase database with:")
    print("  • Project details (area, flats, dates)")
    print("  • Developer information")
    print("  • Building/tower details")
    print("  • Documents")
    print("  • Floor plans")
    print()
    
    # Run the RERA detail scraper
    print(f"Scraping RERA data for: {PROJECT_NAME}")
    print("-" * 80)
    
    try:
        result = subprocess.run(
            ["python", "rera_detail_scraper.py", "--project", PROJECT_NAME, "--pin-code", "500075"],
            cwd=Path(__file__).parent,
            capture_output=False,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            print()
            print("=" * 80)
            print("✅ RERA scraping completed!")
            print("=" * 80)
            print()
            
            # Now import to database
            print("Importing scraped data to Supabase...")
            print("-" * 80)
            
            import_result = subprocess.run(
                ["python", "import_scraped_to_db.py"],
                cwd=Path(__file__).parent,
                capture_output=False,
                text=True,
                check=False
            )
            
            if import_result.returncode == 0:
                print()
                print("=" * 80)
                print("✅ Data imported to Supabase successfully!")
                print("=" * 80)
                print()
                print("You can now check the updated data at:")
                print("https://www.hyderabadurbanrealty.com/property/ALEKHYA%20RISE")
            else:
                print()
                print("=" * 80)
                print("⚠️  Import completed with warnings")
                print("=" * 80)
        else:
            print()
            print("=" * 80)
            print("❌ RERA scraping failed")
            print("=" * 80)
            print()
            print("Possible issues:")
            print("  • Project name might be slightly different in RERA")
            print("  • RERA website might be down")
            print("  • Network connectivity issues")
            sys.exit(1)
            
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ Error: {e}")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
