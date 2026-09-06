# Fix PDF MIME Types - Migration Guide

## Problem
The upload script was incorrectly storing all files with `mime_type = 'image/png'`, including PDFs. This caused PDFs to not display correctly in the frontend.

## Solution
Run the migration script to fix existing records in the database.

## Steps

### 1. Ensure Prerequisites
```bash
pip install psycopg2-binary
```

### 2. Verify Database Connection
Make sure `scrape_preferences.json` has your database connection:
```json
{
  "db_connection": "postgresql://user:pass@host:port/database"
}
```

### 3. Run the Migration
```bash
cd backend
python fix_pdf_mime_types.py
```

### 4. Verify Results
The script will:
- Find all records with `mime_type = 'image/png'` where filename/URL ends with `.pdf`
- Update `mime_type` to `'application/pdf'`
- Update `media_type` to `'document'` if needed
- Show count of fixed records

## What Changed

### Before
```sql
file_name: 'commencement-cert.pdf'
mime_type: 'image/png'        ❌
media_type: 'floorplan'       ❌
```

### After
```sql
file_name: 'commencement-cert.pdf'
mime_type: 'application/pdf'  ✅
media_type: 'document'        ✅
```

## Future Uploads
The `upload_floorplans_to_supabase.py` script has been fixed to automatically detect and set correct MIME types using `mimetypes.guess_type()`.

## Notes
- Safe to run multiple times (idempotent)
- Only updates records that need fixing
- No data loss - only MIME type correction
