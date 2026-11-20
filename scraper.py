import hashlib
import json
import os
import re
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests

# Bot & Channel Config
TELEGRAM_BOT_TOKEN = os.environ.get(
    "BOT_TOKEN", "9222243244:AAHdY4RDyRJuZwT5R9h2_XGUkOnRSZdYIwE"
).strip()
CHANNEL_ID = os.environ.get("VMOU_CHANNEL_ID", "@VmouRajasthan").strip()

SEEN_FILE = "last_seen.json"

# VMOU Main + All 7 Regional Centres & Notices URLs
TARGET_URLS = [
    "https://www.vmou.ac.in/",
    "https://www.vmou.ac.in/regional-centres",
    "https://www.vmou.ac.in/rc-ajmer",
    "https://www.vmou.ac.in/rc-udaipur",
    "https://www.vmou.ac.in/rc-kota",
    "https://www.vmou.ac.in/rc-jaipur",
    "https://www.vmou.ac.in/rc-jodhpur",
    "https://www.vmou.ac.in/rc-bikaner",
    "https://www.vmou.ac.in/rc-bharatpur",
    "https://www.vmou.ac.in/notices",
]

# Regional centre & notice keywords
REGIONAL_CENTRE_KEYWORDS = [
    "ajmer",
    "udaipur",
    "kota",
    "jaipur",
    "jodhpur",
    "bikaner",
    "bharatpur",
    "regional",
    "rcajm",
    "rcudr",
    "rcjpr",
    "rcjdp",
    "rcbkn",
    "rcbpr",
    "rckta",
    "camp",
    "practical",
    "notice",
    "notification",
    "exam",
    "defaulter",
    "assignment",
    "admit",
    "result",
]


def load_seen():
  if os.path.exists(SEEN_FILE):
    try:
      with open(SEEN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
          return {
              "urls": data.get("urls", []) if isinstance(data.get("urls"), list) else [],
              "hashes": data.get("hashes", []) if isinstance(data.get("hashes"), list) else [],
              "notices": data.get("notices", []) if isinstance(data.get("notices"), list) else [],
          }
    except Exception:
      pass
  return {"urls": [], "hashes": [], "notices": []}


def save_seen(seen):
  try:
    payload = {
        "urls": seen.get("urls", [])[-8000:],
        "hashes": seen.get("hashes", [])[-8000:],
        "notices": seen.get("notices", [])[-3000:],
    }
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
      json.dump(payload, f, ensure_ascii=False, indent=2)
  except Exception as e:
    print(f"Error saving {SEEN_FILE}: {e}")


def sha256_bytes(data_bytes):
  return hashlib.sha256(data_bytes).hexdigest()


def sha256_text(text):
  cleaned = " ".join(re.sub(r"\s+", " ", str(text or "").strip().lower()).split())
  return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def detect_rc_label(text):
  low = str(text or "").lower()
  mapping = {
      "ajmer": "Ajmer RC",
      "rcajm": "Ajmer RC",
      "udaipur": "Udaipur RC",
      "rcudr": "Udaipur RC",
      "jaipur": "Jaipur RC",
      "rcjpr": "Jaipur RC",
      "jodhpur": "Jodhpur RC",
      "rcjdp": "Jodhpur RC",
      "bikaner": "Bikaner RC",
      "rcbkn": "Bikaner RC",
      "bharatpur": "Bharatpur RC",
      "rcbpr": "Bharatpur RC",
      "kota": "Kota RC",
      "rckta": "Kota RC",
  }
  for key, label in mapping.items():
    if key in low:
      return label
  return "VMOU Update"


def is_relevant_link(url, text):
  combined = f"{url} {text}".lower()
  if any(ext in combined for ext in [".pdf", ".jpg", ".jpeg", ".png", ".webp"]):
    return True
  return any(kw in combined for kw in REGIONAL_CENTRE_KEYWORDS)


def send_message(text):
  if not CHANNEL_ID:
    print("CHANNEL_ID is empty; skipping sendMessage.")
    return False
  api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  try:
    r = requests.post(
        api_url,
        data={
            "chat_id": CHANNEL_ID,
            "text": text[:4000],
            "disable_web_page_preview": False,
        },
        timeout=25,
    )
    if r.status_code == 429:
      retry_after = int(r.json().get("parameters", {}).get("retry_after", 5))
      time.sleep(retry_after + 1)
      r = requests.post(
          api_url,
          data={
              "chat_id": CHANNEL_ID,
              "text": text[:4000],
              "disable_web_page_preview": False,
          },
          timeout=25,
      )
    if r.status_code != 200:
      print(f"sendMessage failed: {r.text}")
      return False
    return True
  except Exception as e:
    print(f"sendMessage error: {e}")
    return False


def send_document(file_bytes, filename, caption=""):
  if not CHANNEL_ID:
    print("CHANNEL_ID is empty; skipping sendDocument.")
    return False
  api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
  try:
    r = requests.post(
        api_url,
        data={"chat_id": CHANNEL_ID, "caption": caption[:1000]},
        files={"document": (filename, file_bytes)},
        timeout=45,
    )
    if r.status_code == 429:
      retry_after = int(r.json().get("parameters", {}).get("retry_after", 5))
      time.sleep(retry_after + 1)
      r = requests.post(
          api_url,
          data={"chat_id": CHANNEL_ID, "caption": caption[:1000]},
          files={"document": (filename, file_bytes)},
          timeout=45,
      )
    if r.status_code != 200:
      print(f"sendDocument failed ({filename}): {r.text}")
      return False
    return True
  except Exception as e:
    print(f"sendDocument error ({filename}): {e}")
    return False


def send_photo(img_bytes, filename, caption=""):
  if not CHANNEL_ID:
    print("CHANNEL_ID is empty; skipping sendPhoto.")
    return False
  api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
  try:
    r = requests.post(
        api_url,
        data={"chat_id": CHANNEL_ID, "caption": caption[:1000]},
        files={"photo": (filename, img_bytes)},
        timeout=45,
    )
    if r.status_code == 429:
      retry_after = int(r.json().get("parameters", {}).get("retry_after", 5))
      time.sleep(retry_after + 1)
      r = requests.post(
          api_url,
          data={"chat_id": CHANNEL_ID, "caption": caption[:1000]},
          files={"photo": (filename, img_bytes)},
          timeout=45,
      )
    if r.status_code != 200:
      print(f"sendPhoto failed ({filename}): {r.text}")
      return False
    return True
  except Exception as e:
    print(f"sendPhoto error ({filename}): {e}")
    return False


def process_url_item(full_url, title, headers, seen_urls, seen_hashes, seen_notices):
  if full_url in seen_urls:
    return False

  lower_url = full_url.lower()
  rc_tag = detect_rc_label(f"{title} {full_url}")

  # 1. PDF file
  if lower_url.endswith(".pdf") or ".pdf?" in lower_url:
    try:
      resp = requests.get(full_url, headers=headers, timeout=40)
      if resp.status_code == 200 and resp.content:
        h = sha256_bytes(resp.content)
        if h not in seen_hashes:
          fname = os.path.basename(urlparse(full_url).path) or "vmou_notice.pdf"
          if not fname.lower().endswith(".pdf"):
            fname += ".pdf"
          caption = f"[{rc_tag}] {title or 'PDF Notice'}\nJoin @VmouRajasthan".strip()
          if send_document(resp.content, fname, caption):
            seen_urls.add(full_url)
            seen_hashes.add(h)
            print(f"Sent PDF: {fname} ({rc_tag})")
            time.sleep(1.2)
            return True
    except Exception as e:
      print(f"PDF fetch error ({full_url}): {e}")
    return False

  # 2. Image file
  if any(lower_url.endswith(ext) or f"{ext}?" in lower_url for ext in [".jpg", ".jpeg", ".png", ".webp"]):
    try:
      resp = requests.get(full_url, headers=headers, timeout=35)
      if resp.status_code == 200 and resp.content and len(resp.content) > 6000:
        h = sha256_bytes(resp.content)
        if h not in seen_hashes:
          fname = os.path.basename(urlparse(full_url).path) or "vmou_image.jpg"
          caption = f"[{rc_tag}] {title or 'Notice Image'}\nJoin @VmouRajasthan".strip()
          if send_photo(resp.content, fname, caption):
            seen_urls.add(full_url)
            seen_hashes.add(h)
            print(f"Sent Image: {fname} ({rc_tag})")
            time.sleep(1.2)
            return True
    except Exception as e:
      print(f"Image fetch error ({full_url}): {e}")
    return False

  # 3. Sub-page / Notice link
  if title and is_relevant_link(full_url, title):
    n_hash = sha256_text(f"{title}|{full_url}")
    if n_hash not in seen_notices:
      msg = f"[{rc_tag}] {title}\n{full_url}\n\nJoin @VmouRajasthan"
      if send_message(msg):
        seen_urls.add(full_url)
        seen_notices.add(n_hash)
        print(f"Sent Notice: {title} ({rc_tag})")
        time.sleep(1.2)
        return True

  return False


def scrape_page(page_url, headers, seen_urls, seen_hashes, seen_notices, depth=0):
  try:
    resp = requests.get(page_url, headers=headers, timeout=30)
    if resp.status_code != 200:
      print(f"Skipped {page_url}: HTTP {resp.status_code}")
      return
  except Exception as e:
    print(f"Request error on {page_url}: {e}")
    return

  soup = BeautifulSoup(resp.text, "html.parser")
  sub_pages_to_visit = []

  # Sabhi <a> links check karein
  for a in soup.find_all("a", href=True):
    href = a["href"].strip()
    if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
      continue
    full_url = urljoin(page_url, href)
    link_text = " ".join(a.get_text(" ", strip=True).split())

    sent = process_url_item(
        full_url=full_url,
        title=link_text,
        headers=headers,
        seen_urls=seen_urls,
        seen_hashes=seen_hashes,
        seen_notices=seen_notices,
    )

    if (
        not sent
        and depth == 0
        and is_relevant_link(full_url, link_text)
        and full_url not in sub_pages_to_visit
        and "vmou.ac.in" in full_url.lower()
        and not any(full_url.lower().endswith(ext) for ext in [".pdf", ".jpg", ".jpeg", ".png", ".webp", ".zip"])
    ):
      sub_pages_to_visit.append(full_url)

  # Sabhi <img> tags check karein
  for img in soup.find_all("img", src=True):
    src = img["src"].strip()
    if not src or src.startswith("data:"):
      continue
    img_url = urljoin(page_url, src)
    alt_text = " ".join((img.get("alt") or img.get("title") or "").split())
    process_url_item(
        full_url=img_url,
        title=alt_text,
        headers=headers,
        seen_urls=seen_urls,
        seen_hashes=seen_hashes,
        seen_notices=seen_notices,
    )

  # Regional centre ke sub-pages ke andar bhi jaakar PDF/Image/Notices pakdein
  if depth == 0:
    for sub_url in sub_pages_to_visit[:20]:
      scrape_page(
          page_url=sub_url,
          headers=headers,
          seen_urls=seen_urls,
          seen_hashes=seen_hashes,
          seen_notices=seen_notices,
          depth=1,
      )
      time.sleep(0.5)


def main():
  if not TELEGRAM_BOT_TOKEN:
    print("BOT_TOKEN missing.")
    return

  seen = load_seen()
  seen_urls = set(seen.get("urls", []))
  seen_hashes = set(seen.get("hashes", []))
  seen_notices = set(seen.get("notices", []))

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
      )
  }

  for url in TARGET_URLS:
    scrape_page(
        page_url=url,
        headers=headers,
        seen_urls=seen_urls,
        seen_hashes=seen_hashes,
        seen_notices=seen_notices,
        depth=0,
    )

  seen["urls"] = list(seen_urls)
  seen["hashes"] = list(seen_hashes)
  seen["notices"] = list(seen_notices)
  save_seen(seen)
  print("VMOU scraper run completed for @VmouRajasthan.")


if __name__ == "__main__":
  main()
