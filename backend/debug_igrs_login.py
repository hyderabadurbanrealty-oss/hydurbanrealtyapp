"""Debug IGRS login page to find correct user_type values"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=1280,800")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
driver.get("https://registration.telangana.gov.in/districtList.htm")
WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "username")))

print("=== user_type select options ===")
try:
    sel = Select(driver.find_element(By.ID, "user_type"))
    for i, o in enumerate(sel.options):
        print(f"  [{i}] value={o.get_attribute('value')!r:20} text={o.text!r}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n=== All select elements ===")
for sel_el in driver.find_elements(By.TAG_NAME, "select"):
    print(f"  id={sel_el.get_attribute('id')!r} name={sel_el.get_attribute('name')!r}")
    try:
        s = Select(sel_el)
        for o in s.options:
            print(f"    value={o.get_attribute('value')!r:20} text={o.text!r}")
    except: pass

print("\n=== Page title ===")
print(driver.title)
print("\n=== Username field visible? ===")
u = driver.find_element(By.ID, "username")
print(f"  displayed={u.is_displayed()} enabled={u.is_enabled()}")

driver.quit()
