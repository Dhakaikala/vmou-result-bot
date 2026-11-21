from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
import re
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests

TELEGRAM_BOT_TOKEN = os.environ.get(
    "BOT_TOKEN", "9222243244:AAHdY4RDyRJuZwT5R9h2_XGUkOnRSZdYIwE"
).strip()
CHANNEL_USERNAME = "@VmouRajasthan"
PROMO_FOOTER = "✅ VMOU KOTA की अपडेट सबसे पहले Join : @VmouRajasthan"

STATE_FILE = "last_seen.json"

# VMOU & Regional pages monitoring list (5 core VMOU/Regional endpoints)
VMOU_SOURCES = [
    {"name": "VMOU Main Home & Notices", "url": "https://www.vmou.ac.in/"},
    {
        "name": "VMOU Latest News & Announcements",
        "url": "https://www.vmou.ac.in/news",
    },
    {
        "name": "VMOU Examination & Admit Card Updates",
        "url": "https://www.vmou.ac.in/examination",
    },
    {
        "name": "VMOU Assignment & Practical Updates",
        "url": "https://www.vmou.ac.in/assignments",
    },
    {
        "name": "VMOU Regional Centres Directory & Notices",
        "url": "https://www.vmou.ac.in/regional-centres",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
DOC_EXTS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".txt",
    ".csv",
)
SKIP_IMG_KEYWORDS = (
    "logo",
    "icon",
    "favicon",
    "arrow",
    "bullet",
    "social",
    "facebook",
    "twitter",
    "instagram",
    "youtube",
    "whatsapp",
    "naac",
    "spinner",
    "loading",
    "spacer",
)


def clean_text(val):
  return " ".join(str(val or "").strip().split())


def clean_url(url_str):
  return str(url_str or "").strip().strip("()[]\"'").strip()


def make_id(raw_str):
  return hashlib.sha256(str(raw_str or "").encode("utf-8")).hexdigest()[:24]


def get_ist_now_str():
  ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
  return ist_now.strftime("%d-%m-%Y %I:%M %p IST")


def load_state():
  if os.path.exists(STATE_FILE):
    try:
      with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
          seen_ids = (
              data.get("seen_ids", [])
              if isinstance(data.get("seen_ids"), list)
              else []
          )
          seen_urls = (
              data.get("seen_urls", [])
              if isinstance(data.get("seen_urls"), list)
              else []
          )
          return {"seen_ids": seen_ids, "seen_urls": seen_urls}
        if isinstance(data, list):
          return {"seen_ids": [], "seen_urls": [clean_url(x) for x in data]}
    except Exception as e:
      print(f"Error reading {STATE_FILE}: {e}")
  return {"seen_ids": [], "seen_urls": []}


def save_state(state):
  try:
    payload = {
        "updated_at": get_ist_now_str(),
        "seen_ids": state.get("seen_ids", [])[-10000:],
        "seen_urls": state.get("seen_urls", [])[-10000:],
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
      json.dump(payload, f, ensure_ascii=False, indent=2)
  except Exception as e:
    print(f"Error saving {STATE_FILE}: {e}")


def is_vmou_or_regional_link(url_str):
  u = clean_url(url_str).lower()
  if not u.startswith(("http://", "https://")):
    return False
  parsed = urlparse(u)
  if not parsed.netloc:
    return False
  keywords = [
      "vmou",
      "notice",
      "circular",
      "order",
      "exam",
      "result",
      "admit",
      "assignment",
      "practical",
      "regional",
      "jaipur",
      "jodhpur",
      "ajmer",
      "udaipur",
      "kota",
      "bikaner",
      "bharatpur",
      "mercy",
      "notification",
      "timetable",
      "schedule",
      ".pdf",
      ".jpg",
      ".jpeg",
      ".png",
      ".doc",
      ".docx",
  ]
  if "vmou.ac.in" in parsed.netloc:
    return True
  return any(k in u for k in keywords)


def classify_file_type(url_str, content_type=""):
  lower_u = clean_url(url_str).lower().split("?")[0]
  ct = str(content_type or "").lower()
  if lower_u.endswith(IMAGE_EXTS) or ct.startswith("image/"):
    return "image"
  if lower_u.endswith(DOC_EXTS) or "pdf" in ct or "octet-stream" in ct:
    return "document"
  return "link"


def is_likely_ui_asset(url_str, alt_text=""):
  combined = f"{clean_url(url_str).lower()} {clean_text(alt_text).lower()}"
  return any(bad in combined for bad in SKIP_IMG_KEYWORDS)


def extract_items_from_page(source_name, page_url):
  items = []
  try:
    resp = requests.get(clean_url(page_url), headers=HEADERS, timeout=25)
    if resp.status_code != 200:
      print(f"[{source_name}] HTTP {resp.status_code} for {page_url}")
      return items

    soup = BeautifulSoup(resp.text, "html.parser")
    seen_local = set()

    for tag in soup.find_all(["a", "iframe", "embed"]):
      href = tag.get("href") or tag.get("src") or ""
      full_url = clean_url(urljoin(page_url, href))
      if not full_url or full_url.startswith(("javascript:", "mailto:", "#")):
        continue
      if not is_vmou_or_regional_link(full_url):
        continue
      if full_url in seen_local:
        continue
      seen_local.add(full_url)

      title = clean_text(tag.get_text(" ", strip=True))
      if not title or len(title) < 3:
        title = clean_text(
            tag.get("title") or tag.get("aria-label") or ""
        )
      if not title or len(title) < 3:
        path_part = urlparse(full_url).path.split("/")[-1]
        title = clean_text(re.sub(r"[-_]+", " ", path_part)) or "VMOU Update"

      items.append({
          "source": source_name,
          "title": title[:220],
          "url": full_url,
          "kind": classify_file_type(full_url),
      })

    for img in soup.find_all("img"):
      src = clean_url(
          urljoin(
              page_url,
              img.get("src")
              or img.get("data-src")
              or img.get("data-lazy-src")
              or "",
          )
      )
      if not src or src in seen_local:
        continue
      alt_text = clean_text(img.get("alt") or img.get("title") or "")
      if is_likely_ui_asset(src, alt_text):
        continue
      if "vmou.ac.in" in src.lower() or any(
          w in (src + " " + alt_text).lower()
          for w in [
              "notice",
              "exam",
              "mercy",
              "order",
              "circular",
              "regional",
              "result",
              "assignment",
              "upload",
              "media",
              "news",
          ]
      ):
        seen_local.add(src)
        path_name = clean_text(
            re.sub(
                r"[-_]+",
                " ",
                urlparse(src).path.split("/")[-1].rsplit(".", 1)[0],
            )
        )
        final_title = alt_text or path_name or "VMOU Notice Image"
        items.append({
            "source": source_name,
            "title": final_title[:220],
            "url": src,
            "kind": "image",
        })

    print(f"[{source_name}] Found {len(items)} candidate items.")
  except Exception as e:
    print(f"[{source_name}] Error fetching page: {e}")
  return items


def build_caption(item):
  title = clean_text(item.get("title", "VMOU Update"))[:180]
  source = clean_text(item.get("source", "VMOU"))[:75]
  url = clean_url(item.get("url", ""))
  kind = item.get("kind", "link")

  badge = {
      "image": "🖼️ NEW IMAGE NOTICE",
      "document": "📄 NEW PDF / DOC",
      "link": "🔗 NEW UPDATE",
  }.get(kind, "📢 VMOU UPDATE")

  header = f"📢 VMOU KOTA ALERT • {badge}\n\n"
  footer = f"\n\n{PROMO_FOOTER}"

  body_lines = [
      f"📌 {title}",
      f"🏛️ {source}",
  ]
  if url:
    body_lines.append(f"🔗 {url}")

  caption = header + "\n".join(body_lines) + footer
  if len(caption) > 1024:
    max_body_len = 1024 - len(header) - len(footer) - 5
    trimmed_body = ("\n".join(body_lines))[: max(40, max_body_len)]
    caption = header + trimmed_body + "…" + footer
  return caption[:1024]


def download_binary(url_str):
  try:
    r = requests.get(clean_url(url_str), headers=HEADERS, timeout=35)
    if r.status_code == 200 and r.content and len(r.content) > 150:
      ct = r.headers.get("Content-Type", "")
      return r.content, ct
  except Exception as e:
    print(f"Download failed for {url_str}: {e}")
  return None, ""


def send_telegram_item(item):
  if not TELEGRAM_BOT_TOKEN:
    print("Missing BOT_TOKEN.")
    return False

  caption = build_caption(item)
  url = clean_url(item.get("url", ""))
  kind = item.get("kind", "link")
  api_base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

  if kind in ("image", "document") and url:
    content, ct = download_binary(url)
    real_kind = classify_file_type(url, ct)
    if content:
      parsed_name = urlparse(url).path.split("/")[-1] or (
          "vmou_notice.jpg" if real_kind == "image" else "vmou_notice.pdf"
      )
      parsed_name = (
          re.sub(r"[^A-Za-z0-9._-]", "_", parsed_name)[:80] or "vmou_notice"
      )

      if real_kind == "image":
        endpoint = f"{api_base}/sendPhoto"
        files = {"photo": (parsed_name, io.BytesIO(content))}
        data = {
            "chat_id": CHANNEL_USERNAME,
            "caption": caption,
        }
      else:
        if "." not in parsed_name:
          parsed_name += ".pdf"
        endpoint = f"{api_base}/sendDocument"
        files = {"document": (parsed_name, io.BytesIO(content))}
        data = {
            "chat_id": CHANNEL_USERNAME,
            "caption": caption,
        }

      try:
        res = requests.post(endpoint, data=data, files=files, timeout=45)
        if res.status_code == 200:
          return True
        print(f"Media send failed ({endpoint}): {res.text[:220]}")
      except Exception as e:
        print(f"Media post error: {e}")

  msg_text = caption
  if len(msg_text) > 4096:
    msg_text = msg_text[: 4096 - len(PROMO_FOOTER) - 4] + "…\n\n" + PROMO_FOOTER

  try:
    res = requests.post(
        f"{api_base}/sendMessage",
        data={
            "chat_id": CHANNEL_USERNAME,
            "text": msg_text,
            "disable_web_page_preview": False,
        },
        timeout=25,
    )
    if res.status_code == 200:
      return True
    print(f"sendMessage failed: {res.text[:220]}")
    return False
  except Exception as e:
    print(f"sendMessage error: {e}")
    return False


def main():
  if not TELEGRAM_BOT_TOKEN:
    print("BOT_TOKEN missing.")
    return

  state = load_state()
  seen_ids = set(state.get("seen_ids", []))
  seen_urls = set(state.get("seen_urls", []))

  collected = []
  for src in VMOU_SOURCES:
    collected.extend(extract_items_from_page(src["name"], src["url"]))
    time.sleep(0.8)

  new_items = []
  for it in collected:
    u = clean_url(it.get("url", ""))
    t = clean_text(it.get("title", ""))
    item_id = make_id(f"{u}|{t}")
    if item_id not in seen_ids and (not u or u not in seen_urls):
      it["id"] = item_id
      new_items.append(it)

  print(f"Total new VMOU/Regional items detected: {len(new_items)}")
  if not new_items:
    return

  posted = 0
  for it in new_items:
    if send_telegram_item(it):
      seen_ids.add(it["id"])
      if it.get("url"):
        seen_urls.add(clean_url(it["url"]))
      posted += 1
      print(f"Posted ({posted}/{len(new_items)}): {it.get('title')[:70]}")
    time.sleep(1.5)

  if posted > 0:
    state["seen_ids"] = list(seen_ids)
    state["seen_urls"] = list(seen_urls)
    save_state(state)
    print(f"Done! Sent {posted} VMOU updates to {CHANNEL_USERNAME}.")
  else:
    print("No updates were posted. Check bot admin rights in @VmouRajasthan.")


if __name__ == "__main__":
  main()
                
