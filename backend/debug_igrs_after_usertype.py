"""Debug IGRS login page AFTER selecting user_type=1"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
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
WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "user_type")))
time.sleep(2)

# Select user type = 1
driver.execute_script("""
    var sel = document.getElementById('user_type');
    sel.value = '1';
    sel.dispatchEvent(new Event('change'));
""")
time.sleep(3)

print("=== All inputs after user_type=1 ===")
for inp in driver.find_elements(By.TAG_NAME, "input"):
    print(f"  id={inp.get_attribute('id')!r:25} name={inp.get_attribute('name')!r:20} type={inp.get_attribute('type')!r:10} displayed={inp.is_displayed()}")

print("\n=== Page source snippet around form ===")
src = driver.page_source
idx = src.find('id="username"')
if idx > 0:
    print(src[max(0,idx-200):idx+300])
else:
    print("'id=username' NOT FOUND in page source after user_type change")
    # Try to find any input that might be the username
    idx2 = src.find('type="text"')
    if idx2 > 0:
        print("Found text input at:", src[max(0,idx2-100):idx2+200])

driver.quit()
