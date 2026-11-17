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
        f"🔗 <b>डायरेक्ट लिंक / यहाँ क्लिक करें:</b>\n{safe_link}\n\n"
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
  ignore_keywords = [
      "home",
      "about",
      "contact",
      "login",
      "student zone",
      "youtube",
      "facebook",
  ]

  for url in TARGET_URLS:
    try:
      response = requests.get(url, headers=headers, timeout=25, verify=False)
      if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. केवल वास्तविक लिंक्स (जिनका अपना अलग यूआरएल या पीडीएफ है) को पकड़ना
        for a in soup.find_all("a", href=True):
          title = " ".join(a.get_text(strip=True).split())
          href = a["href"].strip()

          # यदि लिंक होमपेज या बेस यूआरएल ही है, तो उसे सीधे छोड़ दें
          if (
              not href
              or href.startswith("javascript:")
              or href.startswith("#")
              or href == "/"
              or href == url
          ):
            continue

          if len(title) > 8:
            if any(
                keyword in title.lower() for keyword in ignore_keywords
            ):
              continue

            full_url = urljoin(url, href)

            # सुनिश्चित करें कि लिंक होमपेज का न हो
            if (
                full_url.rstrip("/") == "https://www.vmou.ac.in"
                or full_url == url
            ):
              continue

            if title not in seen_titles:
              new_found.append({"title": title, "url": full_url})
              seen_titles.add(title)

        # 2. रिजल्ट और परीक्षा की टेबल्स को स्कैन करना (केवल तब जब उनके साथ डायरेक्ट लिंक हो)
        for table in soup.find_all("table"):
          for tr in table.find_all("tr"):
            cols = [
                " ".join(td.get_text(strip=True).split())
                for td in tr.find_all(["td", "th"])
            ]
            if len(cols) >= 2:
              row_text = " | ".join([c for c in cols if c])
              link_tag = tr.find("a", href=True)

              # अगर टेबल रो के अंदर असली और सही लिंक है तभी पोस्ट करें
              if (
                  link_tag
                  and link_tag.get("href")
                  and not link_tag["href"].startswith("#")
                  and not link_tag["href"].startswith("javascript:")
              ):
                item_url = urljoin(url, link_tag["href"])
                if (
                    item_url.rstrip("/") != "https://www.vmou.ac.in"
                    and item_url != url
                ):
                  if len(row_text) > 10 and row_text not in seen_titles:
                    new_found.append({"title": row_text, "url": item_url})
                    seen_titles.add(row_text)

    except Exception as e:
      print(f"Error scraping {url}: {e}")

  if new_found:
    updated_history = new_found + seen_items
    save_history(updated_history[:400])

    for item in reversed(new_found):
      send_telegram_alert(item["title"], item["url"])
      print(f"Posted: {item['title']}")
  else:
    print("No new updates found.")


if __name__ == "__main__":
  scrape_vmou()
