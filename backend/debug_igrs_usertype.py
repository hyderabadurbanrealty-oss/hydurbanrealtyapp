"""Find correct user_type value for Citizen login"""
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
WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "username")))
time.sleep(3)  # let JS finish

# Try each value and check if username becomes visible
for val in ['1', '2', '3', '4']:
    driver.execute_script(f"""
        var sel = document.getElementById('user_type');
        sel.value = '{val}';
        sel.dispatchEvent(new Event('change'));
    """)
    time.sleep(1.5)
    u = driver.find_element(By.ID, "username")
    print(f"  value='{val}' username.displayed={u.is_displayed()} username.enabled={u.is_enabled()}")
    if u.is_displayed():
        print(f"  >>> value='{val}' makes username visible!")
        break

driver.quit()
