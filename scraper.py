import os
import json
import requests
from bs4 import BeautifulSoup
import urllib3

# SSL वार्निंग्स को रोकने के लिए
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TARGET_URLS = [
    "https://www.vmou.ac.in/notices",
    "https://www.vmou.ac.in",
    "https://www.vmou.ac.in/examination"
]
LAST_DATA_FILE = "last_seen.json"

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_media(file_url, title):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Bot Token or Chat ID missing!")
        return
    
    # आपकी डिमांड के अनुसार पूरा कैप्शन और विज्ञापन लाइन बिल्कुल BOLD अक्षरों में
    caption = (
        f"<b>🚨 VMOU KOTA OFFICIAL UPDATE 🚨</b>\n\n"
        f"<b>📌 विषय: {title}</b>\n\n"
        f"<b>✅ VMOU KOTA की अपडेट सबसे पहले Join : @VmouRajasthan</b>"
    )
    
    file_lower = file_url.lower()
    
    # 1. अगर फाइल PDF है तो document की तरह भेजेगा
    if file_lower.endswith(".pdf"):
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        payload = {
            "chat_id": CHAT_ID,
            "document": file_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
    # 2. अगर इमेज है तो photo की तरह भेजेगा
    elif any(file_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": CHAT_ID,
            "photo": file_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
    # 3. अगर नॉर्मल लिंक या वेबपेज है तो टेक्स्ट मैसेज के साथ लिंक भेजेगा
    else:
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        # लिंक को भी बोल्ड फॉर्मेट में सेट किया है
        payload = {
            "chat_id": CHAT_ID,
            "text": f"{caption}\n\n<b>🔗 डायरेक्ट लिंक: <a href='{file_url}'>यहाँ क्लिक करें</a></b>",
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

    try:
        response = requests.post(api_url, json=payload, timeout=25)
        if response.status_code == 200:
            print(f"✅ Successfully sent: {title}")
        else:
            print(f"❌ Telegram API Error: {response.text}")
    except Exception as e:
        print("Error sending to telegram:", e)

def fetch_all_updates():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    all_updates = []
    seen_links = set()
    skip_texts = ["home", "skip to main", "screen reader", "sitemap", "login", "contact us"]

    for url in TARGET_URLS:
        try:
            res = requests.get(url, headers=headers, verify=False, timeout=20)
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
            print(f"Error fetching {url}: {e}")
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

    # सभी वर्तमान लिंक्स को last_seen में जोड़ लें ताकि पुराने मैसेज बार-बार न आएं
    for item in current_updates:
        if item["url"] not in last_seen:
            last_seen.append(item["url"])

    # इतिहास को सेव करें (ताकि बोट को याद रहे)
    with open(LAST_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(last_seen[-1000:], f, ensure_ascii=False, indent=2)

    if new_items:
        print(f"Found {len(new_items)} new updates. Sending to Telegram...")
        # एक बार में अधिकतम 4-5 अपडेट्स भेजेगा ताकि टेलीग्राम सर्वर ब्लॉक न करे
        for item in new_items[:5]:
            send_telegram_media(item['url'], item['title'])
    else:
        print("No new updates found.")

if __name__ == "__main__":
    main()
