import json
import logging
import os
from pathlib import Path

from flask import Flask, abort, request
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
PRODUCT_URL = os.environ.get("PRODUCT_URL", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"
VOICES = json.loads(Path(__file__).with_name("voices.json").read_text(encoding="utf-8"))

SIGNS = [
    ("aries", "♈ Овен"), ("taurus", "♉ Телец"),
    ("gemini", "♊ Близнецы"), ("cancer", "♋ Рак"),
    ("leo", "♌ Лев"), ("virgo", "♍ Дева"),
    ("libra", "♎ Весы"), ("scorpio", "♏ Скорпион"),
    ("sagittarius", "♐ Стрелец"), ("capricorn", "♑ Козерог"),
    ("aquarius", "♒ Водолей"), ("pisces", "♓ Рыбы"),
]
LABELS = dict(SIGNS)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def telegram(method, payload):
    response = requests.post(f"{API}/{method}", json=payload, timeout=15)
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API error"))
    return result


def menu(chat_id):
    buttons = [
        [{"text": label, "callback_data": f"sign:{key}"} for key, label in SIGNS[i:i + 3]]
        for i in range(0, len(SIGNS), 3)
    ]
    telegram("sendMessage", {
        "chat_id": chat_id,
        "text": "🔥 Добро пожаловать!\n\nВыбери свой знак зодиака по дате рождения и получи бесплатный голосовой разбор «Твой денежный ресурс по Солнцу».\n\nЭто один показатель натальной карты, а не персональный прогноз.",
        "reply_markup": {"inline_keyboard": buttons},
    })


def handle_update(update):
    message = update.get("message")
    if message and message.get("chat", {}).get("type") == "private":
        if message.get("text", "").startswith(("/start", "/menu")):
            menu(message["chat"]["id"])
        return

    callback = update.get("callback_query")
    if not callback:
        return
    callback_id = callback["id"]
    data = callback.get("data", "")
    telegram("answerCallbackQuery", {"callback_query_id": callback_id})
    if not data.startswith("sign:"):
        return
    key = data[5:]
    if key not in LABELS:
        return
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    if not chat_id:
        return
    voice_id = VOICES.get(key, "")
    if not voice_id:
        telegram("sendMessage", {"chat_id": chat_id, "text": f"{LABELS[key]}\n\nГолосовой разбор пока готовится. Скоро он появится здесь."})
        return
    telegram("sendVoice", {"chat_id": chat_id, "voice": voice_id})
    if PRODUCT_URL.startswith("https://"):
        telegram("sendMessage", {
            "chat_id": chat_id,
            "text": "Хочешь глубже разобраться в своем денежном сценарии? Узнай о персональном разборе «Карта перерождения».",
            "reply_markup": {"inline_keyboard": [[{"text": "🔥 Подробнее о Карте перерождения", "url": PRODUCT_URL}]]},
        })


@app.get("/")
def health():
    return "Phoenix bot is running", 200


@app.post("/webhook")
def webhook():
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        abort(403)
    update = request.get_json(silent=True)
    if not isinstance(update, dict):
        abort(400)
    try:
        handle_update(update)
    except Exception:
        app.logger.exception("Failed to process Telegram update")
        return "error", 500
    return "ok", 200
