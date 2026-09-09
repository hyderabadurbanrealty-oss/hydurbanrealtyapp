import psycopg2
import json

DB_URL = "postgresql://postgres.qjgwnbszmojzgwmafvuc:LZGJwY0ryKkFKH5P@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

cur.execute("""
    SELECT id, raw_data::text, pricing::text, available_documents
    FROM projects 
    WHERE id = 'ALEKHYA RISE'
""")

row = cur.fetchone()

if row:
    print("\n" + "=" * 120)
    print("RAW DATA for ALEKHYA RISE")
    print("=" * 120)
    
    raw_data = json.loads(row[1]) if row[1] else {}
    pricing = json.loads(row[2]) if row[2] else {}
    docs = row[3] if row[3] else []
    
    # Check for flat/unit information
    print("\n🏢 UNIT INFORMATION:")
    if 'Floor Breakdown' in raw_data:
        print(f"  Floor Breakdown: {len(raw_data['Floor Breakdown'])} entries")
    if 'Building Tower Details' in raw_data:
        print(f"  Building/Tower Details: {len(raw_data['Building Tower Details'])} entries")
        towers = raw_data['Building Tower Details']
        for i, tower in enumerate(towers[:3], 1):
            print(f"    Tower {i}: {tower.get('Name', 'N/A')} - Floors: {tower.get('No. of Floors', 'N/A')}")
    
    print("\n💰 PRICING:")
    if pricing:
        print(f"  Pricing data available: {json.dumps(pricing, indent=2)}")
    else:
        print("  No pricing data")
    
    print("\n📄 DOCUMENTS:")
    print(f"  Total documents: {len(docs)}")
    if docs:
        for i, doc in enumerate(docs[:5], 1):
            print(f"    {i}. {doc}")
        if len(docs) > 5:
            print(f"    ... and {len(docs)-5} more")
    
    # Check for key fields
    print("\n🔑 KEY FIELDS:")
    key_fields = [
        'Project Status', 'Project Type', 'Total Area(In sqmts)', 
        'Net Area(In sqmts)', 'Approved Date', 'Proposed Date of Completion',
        'Name', 'Organization Type'
    ]
    for field in key_fields:
        if field in raw_data:
            print(f"  {field}: {raw_data[field]}")
    
    print("\n" + "=" * 120)
else:
    print("\n❌ Project not found")

cur.close()
conn.close()
