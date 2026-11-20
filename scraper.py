import hashlib
import json
import os
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("VMOU_CHANNEL_ID", "").strip()  # e.g. "@YourChannel" ya "-100..."
SEEN_FILE = "vmou_seen_updates.json"

TARGET_PAGES = [
    "https://www.vmou.ac.in/",
    # Yahan regional centres ya notices ke URLs add karein
]


def load_seen():
  if os.path.exists(SEEN_FILE):
    try:
      with open(SEEN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
          return data
    except Exception:
      pass
  return {"urls": [], "hashes": []}


def save_seen(seen):
  try:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
      json.dump(
          {
              "urls": seen.get("urls", [])[-5000:],
              "hashes": seen.get("hashes", [])[-5000:],
          },
          f,
          ensure_ascii=False,
          indent=2,
      )
  except Exception as e:
    print(f"Error saving vmou history: {e}")


def file_sha256(content_bytes):
  return hashlib.sha256(content_bytes).hexdigest()


def send_text(text):
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  r = requests.post(
      url,
      data={"chat_id": CHANNEL_ID, "text": text[:4000], "disable_web_page_preview": False},
      timeout=25,
  )
  return r.status_code == 200


def send_document_bytes(file_bytes, filename, caption=""):
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
  files = {"document": (filename, file_bytes)}
  data = {"chat_id": CHANNEL_ID, "caption": caption[:1000]}
  r = requests.post(url, data=data, files=files, timeout=40)
  if r.status_code != 200:
    print(f"sendDocument failed ({filename}): {r.text}")
    return False
  return True


def send_photo_bytes(img_bytes, filename, caption=""):
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
  files = {"photo": (filename, img_bytes)}
  data = {"chat_id": CHANNEL_ID, "caption": caption[:1000]}
  r = requests.post(url, data=data, files=files, timeout=40)
  if r.status_code != 200:
    print(f"sendPhoto failed ({filename}): {r.text}")
    return False
  return True


def check_and_post_updates(pages=None):
  if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
    print("Missing BOT_TOKEN or VMOU_CHANNEL_ID.")
    return

  seen = load_seen()
  seen_urls = set(seen.get("urls", []))
  seen_hashes = set(seen.get("hashes", []))
  headers = {"User-Agent": "Mozilla/5.0"}

  for page_url in (pages or TARGET_PAGES):
    try:
      resp = requests.get(page_url, headers=headers, timeout=25)
      if resp.status_code != 200:
        print(f"Page fetch failed {page_url}: {resp.status_code}")
        continue

      soup = BeautifulSoup(resp.text, "html.parser")

      # 1. Sabhi links (PDF aur sub-pages) check karein
      for a_tag in soup.find_all("a", href=True):
        full_url = urljoin(page_url, a_tag["href"].strip())
        link_text = " ".join(a_tag.get_text(" ", strip=True).split())
        lower_url = full_url.lower()

        if lower_url.endswith(".pdf"):
          if full_url in seen_urls:
            continue
          f_resp = requests.get(full_url, headers=headers, timeout=35)
          if f_resp.status_code == 200 and f_resp.content:
            h = file_sha256(f_resp.content)
            if h not in seen_hashes:
              fname = os.path.basename(urlparse(full_url).path) or "vmou_notice.pdf"
              caption = f"VMOU Update (PDF)\n{link_text}\n{full_url}".strip()
              if send_document_bytes(f_resp.content, fname, caption):
                seen_urls.add(full_url)
                seen_hashes.add(h)

      # 2. Sabhi images check karein
      for img_tag in soup.find_all("img", src=True):
        img_url = urljoin(page_url, img_tag["src"].strip())
        alt_text = " ".join((img_tag.get("alt") or "").split())
        if img_url in seen_urls:
          continue
        if any(img_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
          i_resp = requests.get(img_url, headers=headers, timeout=30)
          if i_resp.status_code == 200 and i_resp.content and len(i_resp.content) > 5000:
            h = file_sha256(i_resp.content)
            if h not in seen_hashes:
              fname = os.path.basename(urlparse(img_url).path) or "vmou_update.jpg"
              caption = f"VMOU Update\n{alt_text}\n{img_url}".strip()
              if send_photo_bytes(i_resp.content, fname, caption):
                seen_urls.add(img_url)
                seen_hashes.add(h)

    except Exception as e:
      print(f"Error checking {page_url}: {e}")

  seen["urls"] = list(seen_urls)
  seen["hashes"] = list(seen_hashes)
  save_seen(seen)


if __name__ == "__main__":
  check_and_post_updates()
