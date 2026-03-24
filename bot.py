import json
import requests

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://ungently-somnific-amberly.ngrok-free.dev"

main_keyboard = ReplyKeyboardMarkup(
    [
        [
            KeyboardButton(
                text="📷 Сканувати QR",
                web_app=WebAppInfo(url=f"{API_URL}/miniapp")
            ),
            KeyboardButton("⌨️ Ввести код"),
        ],
        [
            KeyboardButton("ℹ️ Допомога"),
        ],
    ],
    resize_keyboard=True,
)

def get_asset(asset_tag: str):
    try:
        response = requests.get(f"{API_URL}/asset/{asset_tag}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print("API ERROR:", e)
    return None

def format_asset(asset: dict) -> str:
    return (
        f"📦 {asset.get('asset_tag_number', '-')}\n"
        f"📝 {asset.get('item_description', '-')}\n"
        f"🏷 {asset.get('brand_make', '-')}\n"
        f"📐 {asset.get('model', '-')}\n"
        f"📂 {asset.get('asset_classification', '-')} / {asset.get('asset_sub_classification', '-')}\n"
        f"📊 Status: {asset.get('current_status', '-')}\n"
        f"💰 {asset.get('purchase_price', '-')} {asset.get('currency', '')}\n"
        f"🔢 Qty: {asset.get('quantity', '-')}"
    )

async def send_asset_card(update: Update, asset_tag: str):
    asset = get_asset(asset_tag)

    if not asset:
        await update.message.reply_text(
            f"❌ Актив {asset_tag} не знайдено.",
            reply_markup=main_keyboard,
        )
        return

    message = format_asset(asset)
    url = f"{API_URL}/view/{asset_tag}"

    inline_keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔎 Відкрити картку", url=url)]]
    )

    await update.message.reply_text(message, reply_markup=inline_keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 Scanventory\n\n"
        "• знайти актив за інвентарним кодом\n"
        "• показати коротку картку активу\n"
        "• сканувати QR через Telegram Mini App\n\n"
        "Оберіть дію кнопками нижче або надішліть код типу HELP-UKR-0015."
    )
    await update.message.reply_text(text, reply_markup=main_keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "1. Натисніть '📷 Сканувати QR'\n"
        "2. Telegram відкриє Mini App\n"
        "3. Натисніть кнопку сканування\n"
        "4. Після сканування бот покаже картку активу"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == "⌨️ Ввести код":
        await update.message.reply_text(
            "Введіть або вставте код активу, наприклад:\nHELP-UKR-0015",
            reply_markup=main_keyboard,
        )
        return

    if text == "ℹ️ Допомога":
        await help_command(update, context)
        return

    await send_asset_card(update, text)

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw_data = update.message.web_app_data.data
        data = json.loads(raw_data)
        asset_tag = (data.get("asset_tag") or "").strip()

        if not asset_tag:
            await update.message.reply_text(
                "❌ Не вдалося отримати код з Mini App.",
                reply_markup=main_keyboard,
            )
            return

        await send_asset_card(update, asset_tag)

    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Помилка обробки QR:\n{e}",
            reply_markup=main_keyboard,
        )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("🚀 Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()