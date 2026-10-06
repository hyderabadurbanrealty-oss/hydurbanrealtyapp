"""
CAPTCHA Fetcher and Analyzer
Downloads CAPTCHA from RERAIT website and automatically solves it using OCR.
"""

import sys
import os
import requests
import urllib3
from PIL import Image

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL        = "https://rerait.telangana.gov.in"
SEARCH_PAGE_URL = f"{BASE_URL}/SearchList/Search"
CAPTCHA_URL     = f"{BASE_URL}/SearchList/SearchCaptcha"


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
        """
        Solve the RERA blue-dotted-font captcha.

        Pipeline:
          1. Extract blue pixels (text) → black on white
          2. Scale 6x, binarise
          3. Connected-component labelling → keep only the 8 largest blobs
             (letters >> background dots in area)
          4. Run Tesseract with PSM 8/7/13
          5. Post-process: try I→J substitution as an extra candidate
             (Tesseract confuses italic J with I in this font)

        Returns the solved captcha string, or None.
        """
        print("[INFO] Analyzing CAPTCHA...")
        if not os.path.exists(image_path):
            print("File not found.")
            return None

        try:
            import pytesseract
            from collections import deque

            # Locate Tesseract executable
            import shutil as _shutil
            tesseract_exe = _shutil.which('tesseract')
            if not tesseract_exe:
                for path in [
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                    os.path.expandvars(r'%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe'),
                ]:
                    if os.path.exists(path):
                        tesseract_exe = path
                        break
            if not tesseract_exe:
                raise ImportError("tesseract not found in PATH or common install dirs")

            pytesseract.pytesseract.tesseract_cmd = tesseract_exe
            print("Using Tesseract OCR (CCL preprocessing)...")

            # ── Step 1-3: Blue extraction + CCL dot removal ────────────────
            try:
                import numpy as np

                img = Image.open(image_path).convert('RGBA')
                arr = np.array(img)

                # Blue-dominant pixels = text
                blue_mask = (
                    (arr[:,:,2].astype(int) - arr[:,:,0].astype(int) > 30) |
                    (arr[:,:,2].astype(int) - arr[:,:,1].astype(int) > 30)
                )
                bw = np.where(blue_mask, 0, 255).astype(np.uint8)
                img2 = Image.fromarray(bw, 'L')
                img2 = img2.resize((img2.width * 6, img2.height * 6), Image.NEAREST)
                binary = (np.array(img2) < 128).astype(np.uint8)
                h, w = binary.shape

                # BFS connected-component labelling
                label_map = np.zeros((h, w), dtype=np.int32)
                current_label = 0
                component_sizes = {}
                for y in range(h):
                    for x in range(w):
                        if binary[y, x] == 1 and label_map[y, x] == 0:
                            current_label += 1
                            q = deque([(y, x)])
                            label_map[y, x] = current_label
                            size = 0
                            while q:
                                cy, cx = q.popleft()
                                size += 1
                                for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                                    ny, nx = cy+dy, cx+dx
                                    if (0<=ny<h and 0<=nx<w and
                                            binary[ny,nx]==1 and label_map[ny,nx]==0):
                                        label_map[ny, nx] = current_label
                                        q.append((ny, nx))
                            component_sizes[current_label] = size

                # Keep top 8 largest blobs — letters are far larger than dots
                top_labels = set(
                    sorted(component_sizes, key=component_sizes.get, reverse=True)[:8]
                )
                clean = np.ones((h, w), dtype=np.uint8) * 255
                for lbl in top_labels:
                    clean[label_map == lbl] = 0

                from PIL import ImageOps
                result_img = ImageOps.expand(
                    Image.fromarray(clean, 'L'), border=40, fill=255
                )

            except ImportError:
                # numpy not available — simpler fallback
                from PIL import ImageEnhance, ImageFilter
                result_img = Image.open(image_path).convert('L')
                result_img = ImageEnhance.Contrast(result_img).enhance(3.0)
                result_img = result_img.point(lambda p: 0 if p < 128 else 255)
                result_img = result_img.resize(
                    (result_img.width * 4, result_img.height * 4), Image.LANCZOS
                )
                result_img = result_img.filter(ImageFilter.MinFilter(3))

            # ── Step 4: OCR ────────────────────────────────────────────────
            WL  = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            raw = ""
            for psm in (8, 7, 13):
                cfg = f"--oem 3 --psm {psm} -c tessedit_char_whitelist={WL}"
                t   = pytesseract.image_to_string(result_img, config=cfg).strip()
                t   = "".join(c for c in t if c.isalnum()).upper()
                if 4 <= len(t) <= 8:
                    raw = t
                    break
                if len(t) > len(raw):
                    raw = t

            if not raw:
                return None

            # ── Step 5: I→J post-processing ───────────────────────────────
            # The RERA italic serif font causes Tesseract to read J as I.
            # Return the raw OCR result; the retry loop in rera_detail_scraper
            # will also try the I→J substituted variant as a bonus attempt.
            # Store both so the caller can try both without re-downloading.
            self._last_raw    = raw
            self._last_alt    = raw.replace('I', 'J') if 'I' in raw else None
            return raw

        except ImportError:
            pass
        except Exception as e:
            print(f"Tesseract failed: {e}")

        print("Tesseract not found. Trying basic analysis (experimental)...")
        return None


def main():
    print("=" * 40)
    print("  CAPTCHA SOLVER")
    print("=" * 40)
    solver = CaptchaSolver()
    if solver.initialize_session() and solver.download_captcha():
        text = solver.solve_captcha()
        if text:
            print(f"\n DETECTED TEXT: {text}")
            if getattr(solver, '_last_alt', None):
                print(f" ALTERNATE (I->J): {solver._last_alt}")
        else:
            print("\n COULD NOT SOLVE AUTOMATICALLY")


if __name__ == "__main__":
    main()
