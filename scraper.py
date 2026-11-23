from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
import re
import sys
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
import requests

TELEGRAM_BOT_TOKEN = os.environ.get(
    "BOT_TOKEN", "9222243244:AAHdY4RDyRJuZwT5R9h2_XGUkOnRSZdYIwE"
).strip()
CHANNEL_USERNAME = "@VmouRajasthan"
PROMO_FOOTER = "✅ VMOU KOTA की अपडेट सबसे पहले Join : @VmouRajasthan"

STATE_FILE = "last_seen.json"

VMOU_SOURCES = [
    {"name": "VMOU Main Home & Notices", "url": "https://www.vmou.ac.in/"},
    {
        "name": "VMOU Latest News & Announcements",
        "url": "https://www.vmou.ac.in/news",
    },
    {
        "name": "VMOU Online Results Portal",
        "url": "https://online.vmou.ac.in/result.aspx",
    },
    {
        "name": "VMOU Online Student Portal",
        "url": "https://online.vmou.ac.in/",
    },
    {
        "name": "RSCIT / RKCL Result Portal",
        "url": "https://rkcl.vmou.ac.in/",
    },
    {
        "name": "RKCL Official Results",
        "url": "https://www.rkcl.in/",
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
    "banner",
    "slider",
    "header",
    "footer",
    "bg",
    "background",
    "counter",
    "headercounter",
    "headercounterimages",
    "visitor",
    "hitcounter",
    "stats",
    "badge",
    "qr",
    "captcha",
)

SKIP_URL_OR_TEXT = (
    "login",
    "signin",
    "signup",
    "register",
    "privacy",
    "disclaimer",
    "terms",
    "sitemap",
    "contact",
    "about-us",
    "rti",
    "tender",
    "gallery",
    "photo-gallery",
    "video",
    "feedback",
    "helpdesk",
    "forgot",
    "password",
    "headercounterimages",
    "headercounter",
    "hitcounter",
)

UPDATE_KEYWORDS = (
    "notice",
    "notification",
    "circular",
    "order",
    "result",
    "results",
    "rscit",
    "rkcl",
    "exam",
    "examination",
    "admit",
    "hall ticket",
    "timetable",
    "time table",
    "schedule",
    "assignment",
    "practical",
    "camp",
    "regional",
    "jaipur",
    "jodhpur",
    "ajmer",
    "udaipur",
    "kota",
    "bikaner",
    "bharatpur",
    "mercy",
    "revaluation",
    "supplementary",
    "admission",
    "counselling",
    "counseling",
    "date sheet",
    "datesheet",
    "विज्ञप्ति",
    "सूचना",
    "परिणाम",
    "रिजल्ट",
    "परीक्षा",
    "आदेश",
    "प्रवेश पत्र",
    "सत्रीय कार्य",
    "प्रायोगिक",
    "क्षेत्रीय",
)

VOLATILE_QUERY_KEYS = {
    "expires",
    "signature",
    "key-pair-id",
    "policy",
    "x-amz-signature",
    "x-amz-credential",
    "x-amz-date",
    "x-amz-expires",
    "x-amz-security-token",
    "token",
    "ts",
    "time",
    "timestamp",
    "v",
    "ver",
}

_BOLD_UPPER = "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭"
_BOLD_LOWER = "𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇"
_BOLD_DIGIT = "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"


def to_bold(text_str):
  out = []
  for ch in str(text_str or ""):
    if "A" <= ch <= "Z":
      out.append(_BOLD_UPPER[ord(ch) - ord("A")])
    elif "a" <= ch <= "z":
      out.append(_BOLD_LOWER[ord(ch) - ord("a")])
    elif "0" <= ch <= "9":
      out.append(_BOLD_DIGIT[ord(ch) - ord("0")])
    else:
      out.append(ch)
  return "".join(out)


def clean_text(val):
  return " ".join(str(val or "").strip().split())


def clean_url(url_str):
  return str(url_str or "").strip().strip("()[]\"'").strip()


def canonical_url(url_str):
  """Remove volatile signed/cache query params so repeated token refreshes stay identical."""
  u = clean_url(url_str)
  if not u:
    return ""
  try:
    parsed = urlparse(u)
    kept_q = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in VOLATILE_QUERY_KEYS
    ]
    clean_q = urlencode(kept_q)
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path,
        parsed.params,
        clean_q,
        "",
    ))
  except Exception:
    return u.split("?")[0]


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
          norm_urls = [canonical_url(x) for x in seen_urls if clean_url(x)]
          return {"seen_ids": seen_ids, "seen_urls": norm_urls}
        if isinstance(data, list):
          return {
              "seen_ids": [],
              "seen_urls": [canonical_url(x) for x in data if clean_url(x)],
          }
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
  if any(bad in combined for bad in SKIP_IMG_KEYWORDS):
    return True
  # Block numeric-only filenames like "1725618914.png" (often counters/widgets)
  try:
    path_file = urlparse(clean_url(url_str)).path.split("/")[-1]
    stem = path_file.rsplit(".", 1)[0] if "." in path_file else path_file
    if stem.isdigit() and len(stem) >= 6:
      return True
  except Exception:
    pass
  return False


def is_relevant_update(url_str, title_str, kind):
  u = clean_url(url_str).lower()
  t = clean_text(title_str).lower()
  if not u.startswith(("http://", "https://")):
    return False
  parsed = urlparse(u)
  if not parsed.netloc:
    return False
  if any(bad in u or bad in t for bad in SKIP_URL_OR_TEXT):
    return False

  # If title is purely a long number (like counter IDs), skip it
  stripped_t = clean_text(title_str)
  if stripped_t.isdigit() and len(stripped_t) >= 5:
    return False

  if kind == "document" and any(
      d in parsed.netloc for d in ("vmou.ac.in", "rkcl.in", "rkcl.vmou.ac.in")
  ):
    return True

  combined = f"{u} {t}"
  return any(kw in combined for kw in UPDATE_KEYWORDS)


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
      c_url = canonical_url(full_url)
      if c_url in seen_local:
        continue

      title = clean_text(tag.get_text(" ", strip=True))
      if not title or len(title) < 3:
        title = clean_text(tag.get("title") or tag.get("aria-label") or "")
      if not title or len(title) < 3:
        path_part = urlparse(full_url).path.split("/")[-1]
        title = clean_text(re.sub(r"[-_]+", " ", path_part)) or "VMOU Update"

      kind = classify_file_type(full_url)
      if not is_relevant_update(full_url, title, kind):
        continue

      seen_local.add(c_url)
      items.append({
          "source": source_name,
          "title": title[:220],
          "url": full_url,
          "canonical_url": c_url,
          "kind": kind,
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
      if not src:
        continue
      c_url = canonical_url(src)
      if c_url in seen_local:
        continue
      alt_text = clean_text(img.get("alt") or img.get("title") or "")
      if is_likely_ui_asset(src, alt_text):
        continue
      if not is_relevant_update(src, alt_text, "image"):
        continue

      seen_local.add(c_url)
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
          "canonical_url": c_url,
          "kind": "image",
      })

    print(f"[{source_name}] Found {len(items)} relevant items.")
  except Exception as e:
    print(f"[{source_name}] Error fetching page: {e}")
  return items


def build_caption(item):
  title = clean_text(item.get("title", "VMOU Update"))[:140]
  source = clean_text(item.get("source", "VMOU"))[:60]
  url = clean_url(item.get("url", ""))
  kind = item.get("kind", "link")

  badge = {
      "image": to_bold("IMAGE NOTICE"),
      "document": to_bold("PDF / DOC"),
      "link": to_bold("NEW UPDATE"),
  }.get(kind, to_bold("VMOU UPDATE"))

  header = f"📢 {to_bold('VMOU KOTA ALERT')} • {badge}\n\n"
  footer = f"\n\n{PROMO_FOOTER}"

  body_lines = [
      f"📌 {to_bold(title)}",
      f"🏛️ {to_bold(source)}",
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
  seed_only = "--seed-only" in sys.argv
  if not TELEGRAM_BOT_TOKEN and not seed_only:
    print("BOT_TOKEN missing.")
    return

  state = load_state()
  seen_ids = set(state.get("seen_ids", []))
  seen_urls = set(canonical_url(x) for x in state.get("seen_urls", []) if x)

  collected = []
  for src in VMOU_SOURCES:
    collected.extend(extract_items_from_page(src["name"], src["url"]))
    time.sleep(0.8)

  if seed_only:
    seeded = 0
    for it in collected:
      c_u = it.get("canonical_url") or canonical_url(it.get("url", ""))
      t = clean_text(it.get("title", ""))
      item_id = make_id(f"{c_u}|{t}")
      if item_id not in seen_ids:
        seen_ids.add(item_id)
        seeded += 1
      if c_u and c_u not in seen_urls:
        seen_urls.add(c_u)
    state["seen_ids"] = list(seen_ids)
    state["seen_urls"] = list(seen_urls)
    save_state(state)
    print(
        f"Seeded {seeded} existing items into {STATE_FILE} without posting to"
        " Telegram."
    )
    return

  new_items = []
  for it in collected:
    c_u = it.get("canonical_url") or canonical_url(it.get("url", ""))
    t = clean_text(it.get("title", ""))
    item_id = make_id(f"{c_u}|{t}")
    if item_id not in seen_ids and (not c_u or c_u not in seen_urls):
      it["id"] = item_id
      it["canonical_url"] = c_u
      new_items.append(it)

  print(f"Total new VMOU/Regional items detected: {len(new_items)}")
  if not new_items:
    return

  posted = 0
  for it in new_items:
    if send_telegram_item(it):
      seen_ids.add(it["id"])
      if it.get("canonical_url"):
        seen_urls.add(it["canonical_url"])
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
