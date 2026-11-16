import json
import os
import requests
from bs4 import BeautifulSoup
import urllib3

# SSL वार्निंग को बंद करने के लिए
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# यहाँ अपनी असली टेलीग्राम बॉट डिटेल्स और चैनल यूजरनेम डालें
TELEGRAM_BOT_TOKEN = "YOUR_VMOU_BOT_TOKEN_HERE"
CHANNEL_USERNAME = "@YourVMOUChannel"

TARGET_URLS = [
    "https://www.vmou.ac.in/",
    "https://online.vmou.ac.in/results.aspx",
]

HISTORY_FILE = "last_seen.json"


def load_history():
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
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
    
    # साधारण टेक्स्ट फॉर्मेट (ताकि Markdown के किसी सिंबल से मैसेज फेल न हो)
    message = (
        f"🚨 VMOU LIVE UPDATE / RESULT DECLARED! 📚\n\n"
        f"📌 विवरण: {title}\n\n"
        f"🔗 डायरेक्ट लिंक / पोर्टल:\n{link}\n\n"
        "──────────────────────────\n"
        "📢 सबसे तेज़ और पल-पल की अपडेट्स के लिए तुरंत ज्वाइन करें:\n"
        f"👉 {CHANNEL_USERNAME}\n"
        "⚡ हर नया नोटिस, रिजल्ट और पीडीएफ सबसे पहले यहाँ मिलेगा!"
    )

    if ".pdf" in link.lower():
      payload = {
          "chat_id": CHANNEL_USERNAME,
          "document": link,
          "caption": message,
      }
      res = requests.post(api_url + "sendDocument", data=payload, timeout=15)
    else:
      payload = {
          "chat_id": CHANNEL_USERNAME,
          "text": message,
          "disable_web_page_preview": False,
      }
      res = requests.post(api_url + "sendMessage", data=payload, timeout=15)
    print("Telegram API Response:", res.text)
  except Exception as e:
    print(f"Telegram send error: {e}")


def scrape_vmou():
  seen_items = load_history()
  seen_titles = {item["title"] for item in seen_items}
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  new_found = []

  for url in TARGET_URLS:
    try:
      # verify=False जोड़ने से VMOU वेबसाइट का SSL एरर नहीं आएगा
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
    
