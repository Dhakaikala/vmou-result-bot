import json
import os
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# यहाँ अपना टेलीग्राम बॉट टोकन डालें
TELEGRAM_BOT_TOKEN = "YOUR_VMOU_BOT_TOKEN_HERE"
# अपना चैनल यूजरनेम (जैसे @VmouRajasthan) यहाँ डालें
CHANNEL_USERNAME = "@VmouRajasthan"

TARGET_URLS = [
    "https://www.vmou.ac.in/",
    "https://online.vmou.ac.in/results.aspx",
]

HISTORY_FILE = "last_seen.json"


def load_history():
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
          return [item for item in data if isinstance(item, dict) and "title" in item]
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
    
    # एकदम शॉर्ट, आकर्षक कैप्शन और आपकी बताई हुई विज्ञापन लाइन
    message = (
        f"🚨 **VMOU NEW UPDATE / RESULT!** 🎓\n\n"
        f"📌 **{title}**\n\n"
        f"🔗 **डाउनलोड / चेक लिंक:**\n{link}\n\n"
        "──────────────────────────\n"
        f"✅ VMOU KOTA की अपडेट सबसे पहले Join : {CHANNEL_USERNAME}"
    )

    if ".pdf" in link.lower():
      payload = {
          "chat_id": CHANNEL_USERNAME,
          "document": link,
          "caption": message,
          "parse_mode": "Markdown",
      }
      requests.post(api_url + "sendDocument", data=payload, timeout=15)
    else:
      payload = {
          "chat_id": CHANNEL_USERNAME,
          "text": message,
          "parse_mode": "Markdown",
          "disable_web_page_preview": False,
      }
      requests.post(api_url + "sendMessage", data=payload, timeout=15)
  except Exception as e:
    print(f"Telegram send error: {e}")


def scrape_vmou():
  seen_items = load_history()
  seen_titles = {item.get("title") for item in seen_items if isinstance(item, dict)}
  
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  new_found = []

  for url in TARGET_URLS:
    try:
      response = requests.get(url, headers=headers, timeout=20, verify=False)
      if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        for a in soup.find_all("a", href=True):
          title = a.get_text(strip=True)
          href = a["href"]

          if len(title) > 4:
            if href.startswith("http"):
              full_url = href
            elif href.startswith("/"):
              base_domain = (
                  "https://www.vmou.ac.in"
                  if "vmou.ac.in" in url
                  else "https://online.vmou.ac.in"
              )
              full_url = base_domain + href
            else:
              full_url = url + href

            if title not in seen_titles:
              new_found.append({"title": title, "url": full_url})
              seen_titles.add(title)

        for tr in soup.find_all("tr"):
          cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
          row_text = " - ".join([c for c in cols if c])
          if len(row_text) > 8:
            if row_text not in seen_titles:
              new_found.append({"title": row_text, "url": url})
              seen_titles.add(row_text)

    except Exception as e:
      print(f"Error scraping {url}: {e}")

  if new_found:
    updated_history = new_found + seen_items
    save_history(updated_history[:150])

    for item in reversed(new_found):
      send_telegram_alert(item["title"], item["url"])
      print(f"Posted: {item['title']}")
  else:
    print("No new updates found.")


if __name__ == "__main__":
  scrape_vmou()
