import os
import json
import requests
from bs4 import BeautifulSoup

TARGET_URLS = [
    "https://www.vmou.ac.in/notices",
    "https://www.vmou.ac.in",
    "https://www.vmou.ac.in/examination"
]
LAST_DATA_FILE = "last_seen.json"

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print("Error:", e)

def fetch_all_updates():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    all_updates = []
    seen_links = set()
    skip_texts = ["home", "skip to main", "screen reader", "sitemap", "login", "contact us"]

    for url in TARGET_URLS:
        try:
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            for element in soup(["header", "footer", "nav", "script", "style"]):
                element.decompose()

            for a_tag in soup.find_all("a", href=True):
                title = " ".join(a_tag.get_text(strip=True).split())
                link = a_tag["href"].strip()

                if not title or len(title) < 8:
                    continue
                if any(word in title.lower() for word in skip_texts):
                    continue
                if link.startswith("#") or link.startswith("javascript:") or link.startswith("mailto:"):
                    continue

                full_url = link if link.startswith("http") else f"https://www.vmou.ac.in/{link.lstrip('/')}"
                if full_url not in seen_links:
                    seen_links.add(full_url)
                    all_updates.append({"title": title, "url": full_url})
        except Exception as e:
            print(f"Error: {e}")
    return all_updates

def main():
    last_seen = []
    if os.path.exists(LAST_DATA_FILE):
        with open(LAST_DATA_FILE, "r", encoding="utf-8") as f:
            try:
                last_seen = json.load(f)
            except:
                last_seen = []

    current_updates = fetch_all_updates()
    new_items = [item for item in current_updates if item["url"] not in last_seen]

    for item in current_updates:
        if item["url"] not in last_seen:
            last_seen.append(item["url"])

    if new_items:
        for item in new_items[:15]:
            msg = (
                f"🚨 <b>VMOU LIVE UPDATE</b> 🚨\n\n"
                f"📌 <b>विवरण:</b> {item['title']}\n\n"
                f"🔗 <b>क्लिक करके देखें/डाउनलोड करें:</b> {item['url']}\n\n"
                f"📢 <i>Join @VmouRajasthan</i>"
            )
            send_telegram_message(msg)

        with open(LAST_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(last_seen[-300:], f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
  
