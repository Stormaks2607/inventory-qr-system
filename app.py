from typing import Optional
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client

import json
import requests
from fastapi import Body

# =========================
# НАСТРОЙКИ
# =========================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# =========================
# ИНИЦИАЛИЗАЦИЯ
# =========================

app = FastAPI(title="Asset API", version="1.0.0")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
templates = Jinja2Templates(directory="templates")

# =========================
# ЛОГИКА
# =========================

def get_asset_by_tag(asset_tag: str) -> Optional[dict]:
    response = (
        supabase.table("assets")
        .select("*")
        .eq("asset_tag_number", asset_tag)
        .limit(1)
        .execute()
    )
    if response.data:
        return response.data[0]
    return None

# =========================
# API ENDPOINTS
# =========================

@app.get("/")
def root():
    return {"status": "ok", "message": "Inventory system is running"}

@app.get("/asset/{asset_tag}")
def read_asset(asset_tag: str):
    asset = get_asset_by_tag(asset_tag.strip())
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

# =========================
# HTML VIEW (для QR)
# =========================

@app.get("/view/{asset_tag}", response_class=HTMLResponse)
def view_asset(request: Request, asset_tag: str):
    asset = get_asset_by_tag(asset_tag.strip())
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    return templates.TemplateResponse(
        request=request,
        name="asset.html",
        context={"asset": asset},
    )

@app.get("/miniapp", response_class=HTMLResponse)
def miniapp(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="miniapp.html",
        context={},
    )
@app.post("/webhook")
async def telegram_webhook(update: dict = Body(...)):
    token = os.getenv("BOT_TOKEN")

    try:
        print("UPDATE:", update)

        if "message" not in update:
            return {"ok": True}

        message = update["message"]
        chat_id = message["chat"]["id"]

        text = ""

        # 1. Данные из Mini App
        if "web_app_data" in message and message["web_app_data"].get("data"):
            raw_data = message["web_app_data"]["data"]
            try:
                payload = json.loads(raw_data)
                text = (payload.get("asset_tag") or "").strip()
            except Exception:
                text = raw_data.strip()

        # 2. Обычный текст
        elif message.get("text"):
            text = message["text"].strip()

        # 3. Если ничего не получили
        if not text:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "Надішли код активу або натисни кнопку нижче.",
                    "reply_markup": {
                        "keyboard": [
                            [
                                {
                                    "text": "📷 Сканувати QR",
                                    "web_app": {
                                        "url": "https://inventory-qr-system.onrender.com/miniapp"
                                    }
                                },
                                {"text": "⌨️ Ввести код"}
                            ],
                            [{"text": "ℹ️ Допомога"}]
                        ],
                        "resize_keyboard": True
                    }
                },
                timeout=15,
            )
            return {"ok": True}

        if text == "/start":
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": (
                        "Вітаю! Я бот для пошуку активів.\n\n"
                        "Що я вмію:\n"
                        "• знайти актив за кодом\n"
                        "• показати картку активу\n"
                        "• відкрити web-картку\n\n"
                        "Оберіть дію нижче:"
                    ),
                    "reply_markup": {
                        "keyboard": [
                            [
                                {
                                    "text": "📷 Сканувати QR",
                                    "web_app": {
                                        "url": "https://inventory-qr-system.onrender.com/miniapp"
                                    }
                                },
                                {"text": "⌨️ Ввести код"}
                            ],
                            [{"text": "ℹ️ Допомога"}]
                        ],
                        "resize_keyboard": True
                    }
                },
                timeout=15,
            )
            return {"ok": True}

        if text == "⌨️ Ввести код":
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "Введіть код активу, наприклад: HELP-UKR-0015"
                },
                timeout=15,
            )
            return {"ok": True}

        if text == "ℹ️ Допомога":
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "Натисніть '📷 Сканувати QR' або введіть код вручну."
                },
                timeout=15,
            )
            return {"ok": True}

        asset = get_asset_by_tag(text)

        if not asset:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": f"❌ Актив {text} не знайдено."
                },
                timeout=15,
            )
            return {"ok": True}

        message_text = (
            f"📦 {asset.get('asset_tag_number', '-')}\n"
            f"📝 {asset.get('item_description', '-')}\n"
            f"🏷 {asset.get('brand_make', '-')}\n"
            f"📐 {asset.get('model', '-')}\n"
            f"📂 {asset.get('asset_classification', '-')} / {asset.get('asset_sub_classification', '-')}\n"
            f"📊 Status: {asset.get('current_status', '-')}\n"
            f"💰 {asset.get('purchase_price', '-')} {asset.get('currency', '')}\n"
            f"🔢 Qty: {asset.get('quantity', '-')}"
        )

        url = f"https://inventory-qr-system.onrender.com/view/{text}"

        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message_text,
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "🔎 Відкрити картку", "url": url}]
                    ]
                }
            },
            timeout=15,
        )

        return {"ok": True}

    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return {"ok": False, "error": str(e)}