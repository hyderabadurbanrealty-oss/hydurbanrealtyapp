
import json
import requests
from captcha_solver import CaptchaSolver
import os

# Fields in GIS data that may contain pincode info
PINCODE_FIELDS = ['Pincode', 'Pin_Code', 'PinCode', 'PIN_CODE', 'pincode', 'Zip', 'zip']

def _matches_preferences(item: dict, pincodes: list) -> bool:
    """Return True if item matches any of the given pincodes, or if no filter set."""
    if not pincodes:
        return True  # No filter — include everything

    for field in PINCODE_FIELDS:
        val = str(item.get(field, '')).strip()
        if val and val in pincodes:
            return True

    return False

def fetch_all_project_names(filter_pincodes: list = []) -> int:
    """
    Fetch project names from RERA GIS, optionally filtered by pincodes.
    Returns count of saved project names.
    """
    # Initialize the solver to reuse session and SSL config
    solver = CaptchaSolver()
    if not solver.initialize_session():
        print("Failed to initialize session.")
        return 0

    # Endpoint discovered from the 'View All Projects on Map' GIS system
    data_url = "https://rerait.telangana.gov.in/GIS/getData.ashx?GetMapData=Data"
    
    headers = {
        "Referer": "https://rerait.telangana.gov.in/GIS/default.aspx",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }

    print(f"[!] Fetching comprehensive project list from GIS Map systems...")
    try:
        response = solver.session.get(data_url, headers=headers, timeout=60)
        response.raise_for_status()

        try:
            data = response.json()
        except:
            data = json.loads(response.text)

        if isinstance(data, list):
            print(f"[+] Successfully retrieved {len(data)} project records.")

            # Log available fields from first item (helpful for debugging filters)
            if data:
                print(f"[i] Available GIS fields: {list(data[0].keys())}")

            # Apply pincode filter
            active_pincodes = [p.strip() for p in filter_pincodes if p.strip()]

            if active_pincodes:
                print(f"[i] Applying pincode filter: {active_pincodes}")
                filtered = [item for item in data if _matches_preferences(item, active_pincodes)]
                print(f"[+] {len(filtered)}/{len(data)} projects match your pincodes.")
            else:
                print(f"[i] No pincode filter set — including all projects.")
                filtered = data

            # Extract unique project names from filtered set
            project_names = sorted(set(
                item.get("Name_of_Project", "").strip()
                for item in filtered
                if item.get("Name_of_Project", "").strip()
            ))
            print(f"[+] Identified {len(project_names)} unique project names.")

            with open("all_project_names.json", "w", encoding="utf-8") as f:
                json.dump(project_names, f, indent=2)
            print(f"[DONE] Saved to all_project_names.json")
            return len(project_names)
        else:
            print("[-] Error: Unexpected data format from server.")
            return 0

    except Exception as e:
        print(f"[-] Network Error: {e}")
        return 0

if __name__ == "__main__":
    fetch_all_project_names()
