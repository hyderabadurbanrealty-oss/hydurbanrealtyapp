"""
Seeds admin and sample users into Supabase users table.
Uses BCrypt work factor 12, matching the .NET AuthController exactly.

Run:  python seed_users.py
"""
import uuid
import psycopg2
from datetime import datetime, timezone

try:
    import bcrypt
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "bcrypt"])
    import bcrypt

DB_URL = "postgresql://postgres:yxOePamK9RLkgd99@db.qjgwnbszmojzgwmafvuc.supabase.co:5432/postgres"

def hash_password(plain: str) -> str:
    """BCrypt hash with work factor 12 — matches .NET BCrypt.Net.BCrypt.HashPassword(pwd, workFactor:12)"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")

# ── Define users to seed ──────────────────────────────────────────────────────
USERS = [
    # ── Admins ────────────────────────────────────────────────────────────────
    {
        "id":         str(uuid.uuid4()),
        "email":      "admin@hydurban.com",
        "password":   "HydUrban@Admin2024!",
        "full_name":  "HydUrban Admin",
        "mobile":     "+91-9000000001",
        "role":       "admin",
        "is_verified": True,
        "is_active":  True,
    },
    {
        "id":         str(uuid.uuid4()),
        "email":      "hyderabadurbanrealty@gmail.com",
        "password":   "HydUrban@Admin2024!",
        "full_name":  "Hyderabad Urban Realty",
        "mobile":     "+91-9000000002",
        "role":       "admin",
        "is_verified": True,
        "is_active":  True,
    },
    # ── Sample users ──────────────────────────────────────────────────────────
    {
        "id":         str(uuid.uuid4()),
        "email":      "rahul.sharma@example.com",
        "password":   "User@1234!",
        "full_name":  "Rahul Sharma",
        "mobile":     "+91-9876543210",
        "role":       "user",
        "is_verified": True,
        "is_active":  True,
    },
    {
        "id":         str(uuid.uuid4()),
        "email":      "priya.reddy@example.com",
        "password":   "User@1234!",
        "full_name":  "Priya Reddy",
        "mobile":     "+91-9876543211",
        "role":       "user",
        "is_verified": True,
        "is_active":  True,
    },
    {
        "id":         str(uuid.uuid4()),
        "email":      "anil.kumar@example.com",
        "password":   "User@1234!",
        "full_name":  "Anil Kumar",
        "mobile":     "+91-9876543212",
        "role":       "user",
        "is_verified": False,   # unverified — tests email-verification flow
        "is_active":  True,
    },
]

def main():
    print("Connecting to Supabase...")
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    now = datetime.now(timezone.utc)
    inserted = 0
    skipped  = 0

    for u in USERS:
        print(f"  Hashing password for {u['email']} (bcrypt w=12)...", end=" ", flush=True)
        pw_hash = hash_password(u["password"])
        print("done")

        cur.execute("SELECT id FROM users WHERE email = %s", (u["email"],))
        existing = cur.fetchone()

        if existing:
            # Update existing row rather than skip — keeps hash fresh
            cur.execute("""
                UPDATE users SET
                    password_hash     = %s,
                    full_name         = %s,
                    mobile            = %s,
                    role              = %s,
                    is_verified       = %s,
                    is_active         = %s,
                    email_verified_at = %s,
                    updated_at        = %s
                WHERE email = %s
            """, (
                pw_hash, u["full_name"], u["mobile"],
                u["role"], u["is_verified"], u["is_active"],
                now if u["is_verified"] else None,
                now, u["email"]
            ))
            print(f"    UPDATED  {u['role']:5s}  {u['email']}")
            skipped += 1
        else:
            cur.execute("""
                INSERT INTO users (
                    id, email, password_hash, full_name, mobile,
                    role, is_verified, is_active,
                    email_verified_at, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
            """, (
                u["id"], u["email"], pw_hash, u["full_name"], u["mobile"],
                u["role"], u["is_verified"], u["is_active"],
                now if u["is_verified"] else None, now, now
            ))
            print(f"    INSERTED {u['role']:5s}  {u['email']}")
            inserted += 1

    conn.commit()

    # ── Verify ────────────────────────────────────────────────────────────────
    cur.execute("SELECT id, email, full_name, role, is_verified, is_active FROM users ORDER BY role DESC, email")
    rows = cur.fetchall()

    print(f"\n{'─'*70}")
    print(f"{'EMAIL':<40} {'ROLE':<6} {'VERIFIED':<9} {'ACTIVE'}")
    print(f"{'─'*70}")
    for r in rows:
        print(f"{r[1]:<40} {r[3]:<6} {str(r[4]):<9} {r[5]}")
    print(f"{'─'*70}")
    print(f"\nDone — {inserted} inserted, {skipped} updated. Total users: {len(rows)}")

    cur.close()
    conn.close()

    # ── Print credentials summary ─────────────────────────────────────────────
    print("\n" + "="*70)
    print("SEED CREDENTIALS (save these)")
    print("="*70)
    print(f"{'ROLE':<8} {'EMAIL':<40} {'PASSWORD'}")
    print("-"*70)
    for u in USERS:
        print(f"{u['role']:<8} {u['email']:<40} {u['password']}")
    print("="*70)

if __name__ == "__main__":
    main()
