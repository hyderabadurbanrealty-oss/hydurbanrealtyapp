"""Check plan approval status for Alekhya Rise."""
import psycopg2
import json

DB_URL = "postgresql://postgres.qjgwnbszmojzgwmafvuc:LZGJwY0ryKkFKH5P@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

cur.execute("""
    SELECT 
        id, project_name, project_status,
        approved_date, completion_date, revised_completion_date,
        plan_approval_number, survey_number,
        raw_data::text
    FROM projects 
    WHERE id = 'ALEKHYA RISE'
""")

row = cur.fetchone()

if row:
    print("\n" + "=" * 100)
    print("ALEKHYA RISE - PLAN APPROVAL STATUS")
    print("=" * 100)
    
    print(f"\n📋 PROJECT DETAILS:")
    print(f"  Name: {row[1]}")
    print(f"  Status: {row[2]}")
    print(f"  Approved Date: {row[3]}")
    print(f"  Completion Date: {row[4]}")
    print(f"  Revised Completion: {row[5]}")
    
    print(f"\n✅ PLAN APPROVAL:")
    print(f"  Plan Approval Number: {row[6] or 'Not Available'}")
    print(f"  Survey Number: {row[7] or 'Not Available'}")
    
    # Parse raw_data for more approval details
    if row[8]:
        raw_data = json.loads(row[8])
        
        print(f"\n📄 APPROVAL DETAILS FROM RERA:")
        
        # Check for plan approval info
        plan_fields = [
            'Plan Approval Number',
            'Authority Name',
            'Sy.No/TS No.',
            'Approved Date',
            'Approval of Plan',
            'Commencement Certificate',
            'Building Permit'
        ]
        
        for field in plan_fields:
            if field in raw_data:
                value = raw_data[field]
                if value and str(value).strip():
                    print(f"  {field}: {value}")
        
        # Check for documents
        if 'availableDocuments' in raw_data or 'Available Documents' in raw_data:
            docs = raw_data.get('availableDocuments') or raw_data.get('Available Documents', [])
            if docs:
                print(f"\n📑 AVAILABLE DOCUMENTS ({len(docs)} total):")
                # Filter for plan/approval related documents
                plan_docs = [d for d in docs if any(keyword in str(d).lower() 
                    for keyword in ['plan', 'approval', 'sanctioned', 'permit', 'certificate'])]
                
                if plan_docs:
                    for i, doc in enumerate(plan_docs[:10], 1):
                        print(f"  {i}. {doc}")
                    if len(plan_docs) > 10:
                        print(f"  ... and {len(plan_docs)-10} more plan-related documents")
                else:
                    print("  No plan approval documents found")
        
        # Check Development Work section for approval status
        if 'Development Work' in raw_data:
            dev_work = raw_data['Development Work']
            if dev_work and isinstance(dev_work, list):
                print(f"\n🏗️ DEVELOPMENT WORK STATUS:")
                for work in dev_work[:5]:
                    if isinstance(work, dict):
                        name = work.get('Name of Development Work', 'N/A')
                        status = work.get('Stage Of Completion', 'N/A')
                        print(f"  • {name}: {status}")
    
    print("\n" + "=" * 100)
else:
    print("\n❌ Project not found")

# Also check from GIS data
print("\n📍 GIS DATA:")
try:
    with open('alekhya_gis_data.json', 'r') as f:
        gis_data = json.load(f)
        if gis_data:
            project = gis_data[0]
            print(f"  Registration No: {project.get('Registration No.', 'N/A')}")
            print(f"  Application No: {project.get('Application_No', 'N/A')}")
            print(f"  Plot Bearing: {project.get('PlotBearing', 'N/A')}")
            print(f"  Location: {project.get('locality', 'N/A')}")
except FileNotFoundError:
    print("  GIS data file not found")

print()

cur.close()
conn.close()
