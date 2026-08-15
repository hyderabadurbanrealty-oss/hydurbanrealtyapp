"""
seed_unsplash_images.py
========================
Seeds high-quality apartment/building photos from Unsplash
as placeholder images for properties that don't have photos yet.

Unsplash free license: https://unsplash.com/license
Photos are free to use for commercial and non-commercial purposes.
No attribution required (though appreciated).

Run:  python seed_unsplash_images.py
"""
import json, re, requests, psycopg2, time
from pathlib import Path

prefs    = json.loads(Path("scrape_preferences.json").read_text())
DB_URL   = prefs["db_connection"]
SUPA_URL = "https://qjgwnbszmojzgwmafvuc.supabase.co"
SUPA_KEY = prefs["supabase_service_key"]
BUCKET   = "property-media"

# High-quality Unsplash apartment/building photos — curated real estate images
# These are direct Unsplash CDN URLs (free license, no API key needed)
PROPERTY_IMAGES = [
    # Modern apartment complexes & residential towers
    "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=1200&q=80",  # luxury apartment tower
    "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=1200&q=80",  # residential building
    "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1200&q=80",  # modern house
    "https://images.unsplash.com/photo-1600607687939-ce8a6d730c2b?w=1200&q=80",  # luxury interior
    "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=1200&q=80",  # apartment exterior
    "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=1200&q=80",  # modern residence
    "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=1200&q=80",  # white luxury home
    "https://images.unsplash.com/photo-1605146769289-440113cc3d00?w=1200&q=80",  # apartment building
    "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=1200&q=80",  # modern condo
    "https://images.unsplash.com/photo-1583608205776-bfd35f0d9f83?w=1200&q=80",  # residential complex
    "https://images.unsplash.com/photo-1560185007-cde436f6a4d0?w=1200&q=80",  # apartment tower blue
    "https://images.unsplash.com/photo-1574362848149-11496d93a7c7?w=1200&q=80",  # high-rise residential
    "https://images.unsplash.com/photo-1567496898669-ee935f5f647a?w=1200&q=80",  # modern condo exterior
    "https://images.unsplash.com/photo-1595330976519-f34ce9bbf01c?w=1200&q=80",  # luxury apartment pool
    "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=1200&q=80",  # modern interior living
    "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=1200&q=80",  # penthouse view
    "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1200&q=80",  # apartment aerial
    "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1200&q=80",  # modern bedroom
    "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1200&q=80",  # luxury bathroom
    "https://images.unsplash.com/photo-1565182999561-18d7dc61c393?w=1200&q=80",  # apartment complex green
    "https://images.unsplash.com/photo-1619317421569-9e80f9994db7?w=1200&q=80",  # modern tower night
]

def sanitize_id(name): return re.sub(r'[<>:"/\\|?*]', '_', name)

def download_and_upload(image_url: str, storage_path: str) -> str | None:
    try:
        r = requests.get(image_url, timeout=20,
            headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or len(r.content) < 20000:
            return None
        ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        up = requests.post(
            f"{SUPA_URL}/storage/v1/object/{BUCKET}/{storage_path}",
            headers={"Authorization": f"Bearer {SUPA_KEY}", "apikey": SUPA_KEY, "Content-Type": ct},
            data=r.content, timeout=30
        )
        if up.status_code in (200, 201, 409):
            return f"{SUPA_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    except Exception as e:
        print(f"    error: {e}")
    return None

def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    cur.execute("SELECT id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()
    print(f"Seeding placeholder images for {len(projects)} projects...\n")

    uploaded = skipped = 0
    img_idx  = 0  # rotate through image pool

    for project_id, project_name in projects:
        cur.execute(
            "SELECT COUNT(*) FROM project_media WHERE project_id=%s AND media_type='image'",
            (project_id,)
        )
        count = cur.fetchone()[0]
        if count >= 2:
            print(f"  SKIP  {project_name} ({count} images)")
            skipped += 1
            continue

        pid_safe  = sanitize_id(project_name)
        img_url   = PROPERTY_IMAGES[img_idx % len(PROPERTY_IMAGES)]
        img_idx  += 1
        img_url2  = PROPERTY_IMAGES[img_idx % len(PROPERTY_IMAGES)]
        img_idx  += 1

        print(f"  [{project_name}] uploading 2 photos...", end=" ", flush=True)

        for i, url in enumerate([img_url, img_url2]):
            path = f"{pid_safe}/images/placeholder_{i+1}.jpg"
            pub  = download_and_upload(url, path)
            if not pub: continue
            cur.execute("""
                INSERT INTO project_media
                    (id,project_id,media_type,title,file_url,file_name,file_size,mime_type,sort_order)
                VALUES (gen_random_uuid(),%s,'image',%s,%s,'placeholder.jpg',150000,'image/jpeg',%s)
                ON CONFLICT DO NOTHING
            """, (project_id, f"{project_name} — View {i+1}", pub, i))
            conn.commit()
            uploaded += 1

        print("✓")
        time.sleep(0.5)

    cur.close()
    conn.close()
    print(f"\nDone — {uploaded} images uploaded, {skipped} projects skipped")
    print("Note: These are licensed Unsplash placeholder photos.")
    print("Replace them with actual property photos via the Admin → Media Manager.")

if __name__ == "__main__":
    main()
