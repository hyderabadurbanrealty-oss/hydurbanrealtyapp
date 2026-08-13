"""
Seed realistic SRO transaction + unit rate data for Hyderabad.
Run:  python seed_market_data.py
Data is based on real Hyderabad market patterns (2022-2025).
"""
import psycopg2
import random
from datetime import date, timedelta

DB_URL = "host=localhost dbname=hydurban user=hydurban_app password=hydurban"

# ── SRO Transaction seed data ────────────────────────────────────────────────
# Format: (sro_name, district, village, apartment_prefix, base_sqft, vol_per_quarter)
LOCALITIES = [
    ("Serilingampally",  "Ranga Reddy",  "Kondapur",        "KONDAPUR RESIDENCY",    7800,  90),
    ("Serilingampally",  "Ranga Reddy",  "Narsingi",        "NARSINGI HEIGHTS",      6200,  70),
    ("Serilingampally",  "Ranga Reddy",  "Gachibowli",      "GACHIBOWLI TOWERS",     9200,  60),
    ("Serilingampally",  "Ranga Reddy",  "Nalagandla",      "NALAGANDLA ENCLAVE",    7400,  55),
    ("Serilingampally",  "Ranga Reddy",  "Kokapet",         "KOKAPET GREENS",        8100,  65),
    ("Serilingampally",  "Ranga Reddy",  "Tellapur",        "TELLAPUR SPRINGS",      6800,  48),
    ("Rajendranagar",    "Ranga Reddy",  "Manikonda",       "MANIKONDA PLAZA",       5900,  80),
    ("Rajendranagar",    "Ranga Reddy",  "Puppalguda",      "PUPPALGUDA RESIDENCY",  6400,  52),
    ("Rajendranagar",    "Ranga Reddy",  "Nanakramguda",    "NANAKRAMGUDA TOWERS",   8800,  42),
    ("Rajendranagar",    "Ranga Reddy",  "Neknampur",       "NEKNAMPUR GROVE",       5600,  38),
    ("Gandipet",         "Ranga Reddy",  "Osman Nagar",     "OSMAN NAGAR VILLAS",    4800,  30),
    ("Uppal",            "Ranga Reddy",  "Uppal",           "UPPAL ENCLAVE",         4200,  65),
    ("LB Nagar",         "Ranga Reddy",  "LB Nagar",        "LB NAGAR RESIDENCY",   4000,  55),
    ("Kukatpally",       "Hyderabad",    "Kukatpally",      "KUKATPALLY APEX",       5200,  72),
    ("Miyapur",          "Hyderabad",    "Miyapur",         "MIYAPUR HEIGHTS",       5000,  60),
    ("Bachupally",       "Medchal",      "Bachupally",      "BACHUPALLY GREENS",     4600,  50),
    ("Kompally",         "Medchal",      "Kompally",        "KOMPALLY ENCLAVE",      4800,  45),
    ("Ameenpur",         "Sangareddy",   "Ameenpur",        "AMEENPUR GARDENS",      4200,  40),
    ("Nizampet",         "Hyderabad",    "Nizampet",        "NIZAMPET TOWERS",       4900,  42),
    ("Chandanagar",      "Hyderabad",    "Chandanagar",     "CHANDANAGAR HOMES",     5100,  38),
]

# Quarters to generate: Q1 2022 through Q4 2024 (12 quarters)
def gen_quarters():
    qs = []
    for year in [2022, 2023, 2024]:
        for q in range(1, 5):
            qs.append(f"Q{q} {year}")
    return qs

def quarter_to_date_range(q: str):
    parts = q.split()
    qn, yr = int(parts[0][1]), int(parts[1])
    month_start = (qn - 1) * 3 + 1
    start = date(yr, month_start, 1)
    end_month = month_start + 2
    end_day = 28 if end_month == 2 else 30
    end = date(yr, end_month, end_day)
    return start, end

def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

# Price trends — gradually increase QoQ by ~1.5-2.5%
def price_series(base: float, quarters: list) -> list:
    prices = []
    current = base
    for _ in quarters:
        prices.append(current)
        current *= (1 + random.uniform(0.012, 0.025))
    return prices

def seed_sro(conn):
    quarters = gen_quarters()
    rows = []
    flat_counter = {}

    for sro, district, village, apt_prefix, base_sqft, vol in LOCALITIES:
        prices = price_series(base_sqft, quarters)
        flat_counter[village] = flat_counter.get(village, 1000)

        for qi, quarter in enumerate(quarters):
            start, end = quarter_to_date_range(quarter)
            # Add randomness to volume ±30%
            q_vol = max(5, int(vol * random.uniform(0.7, 1.3)))
            avg_price = prices[qi]

            for _ in range(q_vol):
                area_sqft = random.uniform(900, 2400)
                price_psf = avg_price * random.uniform(0.90, 1.10)
                mkt_value = int(area_sqft * price_psf)
                flat_no = f"{random.randint(1, 15)}{chr(random.randint(65, 72))}"
                apt_name = f"{apt_prefix} {random.choice(['BLOCK A','BLOCK B','BLOCK C','TOWER 1','TOWER 2','PHASE 1','PHASE 2'])}"
                reg_date = random_date(start, end)
                flat_counter[village] += 1

                rows.append((
                    sro, district, village,
                    apt_name, flat_no,
                    reg_date, quarter,
                    mkt_value,
                    int(mkt_value * random.uniform(0.85, 0.95)),
                    round(price_psf, 2)
                ))

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE sro_transactions RESTART IDENTITY")
        cur.executemany(
            """INSERT INTO sro_transactions
               (sro_name, district, village, apartment, flat_no, reg_date, quarter,
                mkt_value, cons_value, price_per_sqft, scraped_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())""",
            rows
        )
    conn.commit()
    print(f"✅ Inserted {len(rows):,} SRO transactions across {len(LOCALITIES)} localities and {len(quarters)} quarters")

# ── Unit Rates (Ready Reckoner) seed data ────────────────────────────────────
UNIT_RATES = [
    # district, mandal, locality, search_type, unit_rate_sqft
    ("Ranga Reddy",  "SERILINGAMPALLE", "Kondapur",        "apartment",  5800),
    ("Ranga Reddy",  "SERILINGAMPALLE", "Gachibowli",      "apartment",  7200),
    ("Ranga Reddy",  "SERILINGAMPALLE", "Nalagandla",      "apartment",  5600),
    ("Ranga Reddy",  "SERILINGAMPALLE", "Madhapur",        "apartment",  6400),
    ("Ranga Reddy",  "SERILINGAMPALLE", "Raidurg",         "apartment",  6200),
    ("Ranga Reddy",  "SERILINGAMPALLE", "Hi-Tech City",    "apartment",  7000),
    ("Ranga Reddy",  "SERILINGAMPALLE", "Nanakramguda",    "apartment",  6800),
    ("Ranga Reddy",  "GANDIPET",        "Kokapet",         "apartment",  6000),
    ("Ranga Reddy",  "GANDIPET",        "Narsingi",        "apartment",  4800),
    ("Ranga Reddy",  "GANDIPET",        "Puppalguda",      "apartment",  5000),
    ("Ranga Reddy",  "GANDIPET",        "Tellapur",        "apartment",  5000),
    ("Ranga Reddy",  "GANDIPET",        "Neknampur",       "apartment",  4200),
    ("Ranga Reddy",  "GANDIPET",        "Osman Nagar",     "apartment",  3600),
    ("Ranga Reddy",  "RAJENDRANAGAR",   "Manikonda",       "apartment",  4400),
    ("Ranga Reddy",  "RAJENDRANAGAR",   "Manchirevula",    "apartment",  4000),
    ("Ranga Reddy",  "RAJENDRANAGAR",   "LB Nagar",        "apartment",  3200),
    ("Ranga Reddy",  "UPPAL",           "Uppal",           "apartment",  3200),
    ("Hyderabad",    "SHAIKPET",        "Banjara Hills",   "apartment",  9600),
    ("Hyderabad",    "SHAIKPET",        "Jubilee Hills",   "apartment",  8800),
    ("Hyderabad",    "AMEERPET",        "Kukatpally",      "apartment",  4000),
    ("Hyderabad",    "BALANAGAR",       "Chandanagar",     "apartment",  3800),
    ("Hyderabad",    "BALANAGAR",       "Kompally",        "apartment",  3600),
    ("Hyderabad",    "BACHUPALLY",      "Miyapur",         "apartment",  3800),
    ("Hyderabad",    "BACHUPALLY",      "Bachupally",      "apartment",  3600),
    ("Hyderabad",    "BACHUPALLY",      "Nizampet",        "apartment",  3600),
    ("Medchal",      "BACHUPALLY",      "Kompally",        "apartment",  3400),
    ("Sangareddy",   "AMEENPUR",        "Ameenpur",        "apartment",  3200),
    # Land rates
    ("Ranga Reddy",  "SERILINGAMPALLE", "Kondapur",        "land",       3200),
    ("Ranga Reddy",  "SERILINGAMPALLE", "Gachibowli",      "land",       4500),
    ("Ranga Reddy",  "GANDIPET",        "Kokapet",         "land",       3600),
    ("Ranga Reddy",  "RAJENDRANAGAR",   "Manikonda",       "land",       2400),
    ("Hyderabad",    "SHAIKPET",        "Banjara Hills",   "land",       6400),
    ("Hyderabad",    "AMEERPET",        "Kukatpally",      "land",       2200),
    ("Sangareddy",   "AMEENPUR",        "Ameenpur",        "land",       1800),
]

def seed_unit_rates(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE unit_rates RESTART IDENTITY")
        cur.executemany(
            """INSERT INTO unit_rates (district, mandal, locality, search_type, unit_rate_sqft, scraped_at)
               VALUES (%s,%s,%s,%s,%s,NOW())""",
            UNIT_RATES
        )
    conn.commit()
    print(f"✅ Inserted {len(UNIT_RATES)} unit rate rows")

if __name__ == "__main__":
    random.seed(42)  # reproducible
    print("Connecting to database…")
    conn = psycopg2.connect(DB_URL)
    print("Seeding SRO transactions…")
    seed_sro(conn)
    print("Seeding unit rates…")
    seed_unit_rates(conn)
    conn.close()
    print("Done! Restart the .NET backend to pick up the new data.")
