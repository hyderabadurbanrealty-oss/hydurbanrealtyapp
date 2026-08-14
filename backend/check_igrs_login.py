"""Check current IGRS login page field IDs"""
import requests
from bs4 import BeautifulSoup

resp = requests.get("https://registration.telangana.gov.in/districtList.htm", timeout=15)
soup = BeautifulSoup(resp.text, "html.parser")

print("Input fields found:")
for inp in soup.find_all("input"):
    print(f"  id={inp.get('id')!r:30} name={inp.get('name')!r:30} type={inp.get('type')!r}")

print("\nForms found:")
for form in soup.find_all("form"):
    print(f"  id={form.get('id')!r} action={form.get('action')!r}")
