import html
import json
import os
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# आपका टेलीग्राम बॉट टोकन और चैनल
TELEGRAM_BOT_TOKEN = "9099367147:AAEIZMehH4Sw45u2Vj3XfvyL693Rn73C6l8"
CHANNEL_USERNAME = "@VmouRajasthan"

TARGET_URLS = [
    "https://www.vmou.ac.in/",
    "https://online.vmou.ac.in/results.aspx",
    "https://result.vmou.ac.in/",
    "https://rkcl.vmou.ac.in/",
    "https://admissions.vmou.ac.in/",
    "https://exam.vmou.ac.in/",
]

HISTORY_FILE = "last_seen.json"


def load_history():
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
          return [
              item
              for item in data
              if isinstance(item, dict) and "title" in item
          ]
    except Exception:
      pass
  return []


def save_history(history_list):
  try:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
      json.dump(history_list, f, ensure_ascii=False, indent=4)
  except Exception as e:
    print(f"Error saving history: {e}")


def send_telegram_alert(title, link):
  try:
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/"
    safe_title = html.escape(title)
    safe_link = html.escape(link)

    message = (
        f"🚨 <b>VMOU KOTA NEW UPDATE / RESULT!</b> 🎓\n\n"
        f"📌 <b>{safe_title}</b>\n\n"
        f"🔗 <b>डायरेक्ट लिंक / चेक करें:</b>\n{safe_link}\n\n"
        "──────────────────────────\n"
        f"✅ <b>VMOU KOTA की अपडेट सबसे पहले Join : {CHANNEL_USERNAME}</b>"
    )

    if ".pdf" in link.lower() or "pdf" in link.lower():
      payload = {
          "chat_id": CHANNEL_USERNAME,
          "document": link,
          "caption": message,
          "parse_mode": "HTML",
      }
      res = requests.post(api_url + "sendDocument", data=payload, timeout=15)
    else:
      payload = {
          "chat_id": CHANNEL_USERNAME,
          "text": message,
          "parse_mode": "HTML",
          "disable_web_page_preview": False,
      }
      res = requests.post(api_url + "sendMessage", data=payload, timeout=15)

    if res.status_code != 200:
      print(f"Telegram API Error: {res.text}")
  except Exception as e:
    print(f"Telegram send error: {e}")


def scrape_vmou():
  seen_items = load_history()
  seen_titles = {
      item.get("title") for item in seen_items if isinstance(item, dict)
  }

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  new_found = []

  for url in TARGET_URLS:
    try:
      response = requests.get(url, headers=headers, timeout=25, verify=False)
      if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. साइट की हर एक टेबल की रो (Row) को बिना किसी शर्त के सीधा उठाना (जैसे रिजल्ट्स)
        for table in soup.find_all("table"):
          for tr in table.find_all("tr"):
            cols = [
                " ".join(td.get_text(strip=True).split())
                for td in tr.find_all(["td", "th"])
            ]
            if len(cols) >= 2:
              row_text = " | ".join([c for c in cols if c])
              if len(row_text) > 6 and row_text not in seen_titles:
                a_tag = tr.find("a", href=True)
                item_url = (
                    urljoin(url, a_tag["href"]) if (a_tag and a_tag.get("href")) else url
                )
                new_found.append({"title": row_text, "url": item_url})
                seen_titles.add(row_text)

        # 2. साइट के हर एक टेक्स्ट, लिंक, लिस्ट या नोटिस को बिना रोके उठाना
        for tag in soup.find_all(
            ["a", "marquee", "li", "p", "span", "h1", "h2", "h3", "h4", "div"]
        ):
          title = " ".join(tag.get_text(strip=True).split())
          href = tag.get("href", "").strip() if tag.name == "a" else ""

          if len(title) > 8 and not title.lower().startswith("http"):
            item_url = urljoin(url, href) if href else url
            if title not in seen_titles:
              new_found.append({"title": title, "url": item_url})
              seen_titles.add(title)

    except Exception as e:
      print(f"Error scraping {url}: {e}")

  if new_found:
    updated_history = new_found + seen_items
    save_history(updated_history[:800])

    for item in reversed(new_found):
      send_telegram_alert(item["title"], item["url"])
      print(f"Posted: {item['title']}")
  else:
    print("No new updates found.")


if __name__ == "__main__":
  scrape_vmou()
