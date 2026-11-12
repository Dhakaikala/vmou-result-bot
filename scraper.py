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

def send_telegram_media(file_url, caption):
    if not BOT_TOKEN or not CHAT_ID:
        return
    
    file_lower = file_url.lower()
    
    # चेक करेंगे कि फाइल PDF है या इमेज (jpg, png, jpeg)
    if file_lower.endswith(".pdf"):
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        payload = {
            "chat_id": CHAT_ID,
            "document": file_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
    elif any(file_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHAT_ID,
            "photo": file_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
    else:
        # अगर नॉर्मल वेब पेज लिंक है (या डायरेक्ट फाइल नहीं है), तो साधारण मैसेज भेजेंगे
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": f"{caption}\n\n🔗 <b>लिंक:</b> {file_url}",
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

    try:
        requests.post(api_url, json=payload, timeout=20)
    except Exception as e:
        print("Error sending media:", e)

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
        # एक बार में 4-5 अपडेट्स भेजेगा ताकि सर्वर पर लोड न पड़े
        for item in new_items[:5]:
            
            # आपकी डिमांड के अनुसार कैप्शन पूरी तरह से BOLD अक्षरों में और विज्ञापन लाइन के साथ
            caption = (
                f"<b>🚨 VMOU KOTA OFFICIAL UPDATE 🚨</b>\n\n"
                f"<b>📌 विषय: {item['title']}</b>\n\n"
                f"<b>✅ VMOU KOTA की अपडेट सबसे पहले Join : @VmouRajasthan</b>"
            )
