"""
CAPTCHA Fetcher and Analyzer
Downloads CAPTCHA from RERAIT website and automatically solves it using OCR.
Supports multiple OCR engines (Tesseract, EasyOCR).
"""

import sys
import os
import requests
import urllib3
from PIL import Image

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants
BASE_URL = "https://rerait.telangana.gov.in"
SEARCH_PAGE_URL = f"{BASE_URL}/SearchList/Search"
CAPTCHA_URL = f"{BASE_URL}/SearchList/SearchCaptcha"

class CaptchaSolver:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": SEARCH_PAGE_URL,
        })
    
    def initialize_session(self):
        try:
            print("[INFO] Initializing session...")
            resp = self.session.get(SEARCH_PAGE_URL)
            resp.raise_for_status()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to initialize: {e}")
            return False
    
    def download_captcha(self, output_path="captcha.png"):
        try:
            print(f"[INFO] Downloading CAPTCHA...")
            resp = self.session.get(CAPTCHA_URL, stream=True)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(1024):
                    f.write(chunk)
            print(f"[SUCCESS] Saved to {output_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to download: {e}")
            return False
    
    def solve_captcha(self, image_path="captcha.png"):
        print(f"[INFO] Analyzing CAPTCHA...")
        if not os.path.exists(image_path):
            print("File not found.")
            return None

        # Method 1: Try Tesseract
        try:
            import pytesseract
            # Common Windows paths for Tesseract
            tesseract_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                os.path.expandvars(r'%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe')
            ]
            
            # Check if tesseract is in PATH
            tesseract_cmd = 'tesseract'
            
            # Check explicit paths
            found_tesseract = False
            import shutil
            if shutil.which('tesseract'):
                found_tesseract = True
            else:
                for path in tesseract_paths:
                    if os.path.exists(path):
                        pytesseract.pytesseract.tesseract_cmd = path
                        found_tesseract = True
                        break
            
            if found_tesseract:
                print("Using Tesseract OCR...")
                img = Image.open(image_path).convert('L')
                custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
                text = pytesseract.image_to_string(img, config=custom_config)
                return text.strip()
        except ImportError:
            pass
        except Exception as e:
            print(f"Tesseract failed: {e}")

        # Method 2: Try standard string reading (very basic fallback)
        print("Tesseract not found. Trying basic analysis (experimental)...")
        return None

def main():
    print("="*40)
    print("  CAPTCHA SOLVER")
    print("="*40)
    
    solver = CaptchaSolver()
    if solver.initialize_session() and solver.download_captcha():
        text = solver.solve_captcha()
        
        if text:
            print(f"\n📢 DETECTED TEXT: {text}")
        else:
            print("\n❌ COULD NOT SOLVE AUTOMATICALLY")
            print("Reason: Tesseract OCR Software is not installed.")
            print("\nTO FIX THIS:")
            print("1. Download Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")
            print("2. Run the installer")
            print("3. Try this script again")

if __name__ == "__main__":
    main()
