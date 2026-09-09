"""
Fetch Alekhya Rise data from RERA GIS system.

The GIS system (https://rerait.telangana.gov.in/GIS/default.aspx) provides:
- Project location coordinates
- Basic project information
- All projects in a pincode

Usage:
    python fetch_alekhya_from_gis.py
"""
import json
import requests
from captcha_solver import CaptchaSolver

def fetch_gis_data():
    """Fetch all project data from RERA GIS."""
    print("=" * 80)
    print("Fetching project data from RERA GIS System")
    print("=" * 80)
    print()
    
    solver = CaptchaSolver()
    if not solver.initialize_session():
        print("❌ Failed to initialize session.")
        return []
    
    data_url = "https://rerait.telangana.gov.in/GIS/getData.ashx?GetMapData=Data"
    
    headers = {
        "Referer": "https://rerait.telangana.gov.in/GIS/default.aspx",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    print("📡 Fetching data from GIS Map system...")
    
    try:
        response = solver.session.get(data_url, headers=headers, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        if isinstance(data, list):
            print(f"✅ Retrieved {len(data)} project records")
            return data
        else:
            print("❌ Unexpected data format")
            return []
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def find_alekhya_projects(all_data):
    """Find all projects with 'Alekhya' in the name."""
    print()
    print("🔍 Searching for Alekhya projects...")
    print("-" * 80)
    
    alekhya_projects = [
        item for item in all_data
        if item.get("Name_of_Project", "").strip() and 
        "alekhya" in item.get("Name_of_Project", "").lower()
    ]
    
    if not alekhya_projects:
        print("❌ No projects found with 'Alekhya' in name")
        return []
    
    print(f"✅ Found {len(alekhya_projects)} Alekhya project(s)")
    print()
    
    for i, project in enumerate(alekhya_projects, 1):
        print(f"Project {i}:")
        print(f"  Name: {project.get('Name_of_Project', 'N/A')}")
        print(f"  Registration No: {project.get('Registration_No', 'N/A')}")
        print(f"  Location: {project.get('Locality', 'N/A')}")
        print(f"  Pincode: {project.get('Pincode', 'N/A')}")
        print(f"  Status: {project.get('Status', 'N/A')}")
        print(f"  Latitude: {project.get('Latitude', 'N/A')}")
        print(f"  Longitude: {project.get('Longitude', 'N/A')}")
        print(f"  Promoter: {project.get('Promoter_Name', 'N/A')}")
        
        # Show all available fields
        print(f"  Available fields: {', '.join(project.keys())}")
        print("-" * 80)
    
    return alekhya_projects


def find_pincode_500075_projects(all_data):
    """Find all projects in pincode 500075."""
    print()
    print("🔍 Searching for all projects in pincode 500075...")
    print("-" * 80)
    
    pincode_projects = [
        item for item in all_data
        if str(item.get("Pincode", "")).strip() == "500075" or
        str(item.get("Pin_Code", "")).strip() == "500075"
    ]
    
    if not pincode_projects:
        print("❌ No projects found in pincode 500075")
        return []
    
    print(f"✅ Found {len(pincode_projects)} project(s) in pincode 500075")
    print()
    
    for i, project in enumerate(pincode_projects, 1):
        print(f"{i}. {project.get('Name_of_Project', 'N/A')} - {project.get('Locality', 'N/A')}")
    
    return pincode_projects


def main():
    # Fetch all GIS data
    all_data = fetch_gis_data()
    
    if not all_data:
        return
    
    # Find Alekhya projects
    alekhya_projects = find_alekhya_projects(all_data)
    
    # Save Alekhya project data
    if alekhya_projects:
        with open("alekhya_gis_data.json", "w", encoding="utf-8") as f:
            json.dump(alekhya_projects, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved detailed data to: alekhya_gis_data.json")
    
    # Also show all projects in same pincode
    pincode_projects = find_pincode_500075_projects(all_data)
    
    if pincode_projects:
        with open("pincode_500075_projects.json", "w", encoding="utf-8") as f:
            json.dump(pincode_projects, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved pincode 500075 projects to: pincode_500075_projects.json")
    
    print()
    print("=" * 80)
    print("✅ GIS data fetch completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
