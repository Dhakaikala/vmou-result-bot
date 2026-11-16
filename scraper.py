import asyncio
import json
import os
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# आपकी बॉट और चैनल डिटेल्स
TELEGRAM_BOT_TOKEN = "YOUR_VMOU_BOT_TOKEN_HERE"  # अपना बोट टोकन यहाँ डालें
CHANNEL_USERNAME = "@YourVMOUChannel"  # अपना टेलीग्राम चैनल यूजरनेम यहाँ डालें

DB_FILE = "vmou_strict_db.json"

# जिन दो मुख्य लिंक्स को यह बोट लगातार ट्रैक करेगा
TARGET_URLS = [
    "https://www.vmou.ac.in/",
    "https://online.vmou.ac.in/results.aspx",
]


def load_saved_data():
  if os.path.exists(DB_FILE):
    try:
      with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      pass
  return []


def save_data_to_file(data_list):
  try:
    with open(DB_FILE, "w", encoding="utf-8") as f:
      json.dump(data_list, f, ensure_ascii=False, indent=4)
  except Exception as e:
    print(f"Database save error: {e}")


CACHED_ITEMS = load_saved_data()
SEEN_TITLES = {item["title"] for item in CACHED_ITEMS}

app = Flask(__name__)


@app.route("/")
def home():
  return f"VMOU Multi-URL Strict Tracker Active! Total Tracked: {len(CACHED_ITEMS)}"


def run_flask():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


# दोनों वेबसाइट्स से हर छोटे-बड़े अपडेट, रिजल्ट और PDF को स्कैन करने का फंक्शन
def fetch_vmou_strict_updates():
  new_updates = []
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  for url in TARGET_URLS:
    try:
      response = requests.get(url, headers=headers, timeout=12)
      if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. सभी लिंक्स और PDF को स्कैन करना
        for a in soup.find_all("a", href=True):
          title = a.get_text(strip=True)
          href = a["href"]

          if len(title) > 4:
            # पूर्ण लिंक बनाना
            if href.startswith("http"):
              full_url = href
            elif href.startswith("/"):
              # डोमेन एक्सट्रेक्ट करना
              base_domain = "https://www.vmou.ac.in" if "vmou.ac.in" in url else "https://online.vmou.ac.in"
              full_url = base_domain + href
            else:
              full_url = url + href

            # यदि कोई भी नया रिजल्ट, नोटिस या PDF मिलता है
            if title not in SEEN_TITLES:
              new_updates.append({
                  "title": title,
                  "url": full_url,
                  "source": url,
              })

        # 2. टेबल्स से रिजल्ट्स या घोषणाओं को निकालना (खासकर results.aspx के लिए)
        for tr in soup.find_all("tr"):
          cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
          row_text = " - ".join([c for c in cols if c])
          if len(row_text) > 8:
            if row_text not in SEEN_TITLES:
              new_updates.append({
                  "title": row_text,
                  "url": url,
                  "source": url,
              })

    except Exception as e:
      print(f"Error fetching {url}: {e}")

  return new_updates


# बैकग्राउंड वर्कर जो लगातार नजर रखेगा और चैनल पर विज्ञापन/कैप्शन के साथ पोस्ट करेगा
async def background_tracker(application):
  global CACHED_ITEMS, SEEN_TITLES

  while True:
    loop = asyncio.get_running_loop()
    updates = await loop.run_in_executor(None, fetch_vmou_strict_updates)

    if updates:
      updated_flag = False
      for item in updates:
        title = item["title"]
        link = item["url"]

        if title not in SEEN_TITLES:
          SEEN_TITLES.add(title)
          CACHED_ITEMS.insert(0, item)
          updated_flag = True

          try:
            # विज्ञापन लाइन और खूबसूरत कैप्शन के साथ मैसेज फॉर्मेट
            channel_msg = (
                "🚨 **VMOU LIVE UPDATE / RESULT DECLARED!** 📚\n\n"
                f"📌 **विवरण:** {title}\n\n"
                f"🔗 **डायरेक्ट लिंक / पोर्टल:**\n{link}\n\n"
                "──────────────────────────\n"
                "📢 **सबसे तेज़ और पल-पल की अपडेट्स के लिए तुरंत ज्वाइन करें:**\n"
                f"👉 {CHANNEL_USERNAME}\n"
                "⚡ *हर नया नोटिस, रिजल्ट और पीडीएफ सबसे पहले यहाँ मिलेगा!*"
            )

            # अगर अपडेट में डायरेक्ट PDF फाइल है, तो उसे डॉक्यूमेंट के रूप में भेजें
            if ".pdf" in link.lower():
              await application.bot.send_document(
                  chat_id=CHANNEL_USERNAME,
                  document=link,
                  caption=channel_msg,
                  parse_mode="Markdown",
              )
            else:
              await application.bot.send_message(
                  chat_id=CHANNEL_USERNAME,
                  text=channel_msg,
                  parse_mode="Markdown",
                  disable_web_page_preview=False,
              )
          except Exception as e:
            print(f"Telegram posting error: {e}")

      if updated_flag:
        save_data_to_file(CACHED_ITEMS)

    # हर 3 मिनट में दोनों वेबसाइट्स की जाँच करेगा ताकि एक सेकंड की भी देरी न हो
    await asyncio.sleep(180)


async def post_init(application):
  asyncio.create_task(background_tracker(application))


# /start कमांड
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_name = (
      update.effective_user.first_name
      if update.effective_user
      else "Student"
  )
  welcome_text = (
      f"Radhe Radhe {user_name} ji! 🙏\n\n"
      "🎓 **VMOU Strict Multi-URL Tracker Bot**\n"
      "⚡ `vmou.ac.in` और `online.vmou.ac.in/results.aspx` पर हर छोटी-बड़ी अपडेट पर नजर रखे हुए है।\n\n"
      "👇 नीचे दिए गए बटन से ताज़ा अपडेट्स देखें:"
  )

  keyboard = [
      [
          InlineKeyboardButton(
              "📋 Latest Live Updates", callback_data="get_live"
          )
      ],
      [
          InlineKeyboardButton(
              "📢 Join Official Channel", url="https://t.me/YourVMOUChannel"
          )
      ],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  if update.message:
    await update.message.reply_text(
        welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
    )
  elif update.callback_query:
    await update.callback_query.message.edit_text(
        welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
    )


# बटन हैंडलर
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  data = query.data

  back_keyboard = InlineKeyboardMarkup(
      [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
  )

  if data == "get_live":
    text = "📚 **VMOU Tracked Live Updates & Results:**\n\n"
    items = (
        CACHED_ITEMS[:12] if CACHED_ITEMS else fetch_vmou_strict_updates()
    )

    if items:
      for i, item in enumerate(items[:10], 1):
        text += f"📌 {i}. [{item['title']}]({item['url']})\n\n"
    else:
      text = "⚠️ अभी कोई नया डेटा सिंक नहीं हुआ है।"

    await query.message.edit_text(
        text,
        reply_markup=back_keyboard,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )

  elif data == "main_menu":
    await start(update, context)


def main():
  flask_thread = threading.Thread(target=run_flask)
  flask_thread.daemon = True
  flask_thread.start()

  application = (
      ApplicationBuilder()
      .token(TELEGRAM_BOT_TOKEN)
      .post_init(post_init)
      .build()
  )

  application.add_handler(CommandHandler("start", start))
  application.add_handler(CallbackQueryHandler(button_handler))

  print("VMOU Multi-URL Strict Tracker is live...")
  application.run_polling()


if __name__ == "__main__":
  main()
