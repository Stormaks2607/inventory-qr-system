import json
import os

import requests
from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import app as inventory_app

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://inventory-qr-system.onrender.com"

main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("My assets")],
        [
            KeyboardButton(
                text="Scan QR",
                web_app=WebAppInfo(url=f"{API_URL}/miniapp"),
            ),
            KeyboardButton("Enter code"),
        ],
        [KeyboardButton("Help")],
    ],
    resize_keyboard=True,
)

auth_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Share phone number", request_contact=True)],
        [KeyboardButton("Help")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def get_asset(asset_tag: str):
    try:
        response = requests.get(f"{API_URL}/asset/{asset_tag}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as exc:
        print("API ERROR:", exc)
    return None


def format_asset(asset: dict) -> str:
    assignment = asset.get("current_assignment") or {}
    effective_status = assignment.get("status") or asset.get("current_status") or "-"
    assignment_date = assignment.get("assignment_date") or "-"

    return (
        f"📦 Asset: {asset.get('asset_tag_number', '-')}\n"
        f"📝 Description: {asset.get('item_description', '-')}\n"
        f"🏷️ Brand: {asset.get('brand_make', '-')}\n"
        f"📐 Model: {asset.get('model', '-')}\n"
        f"📂 Classification: {asset.get('asset_classification', '-')} / "
        f"{asset.get('asset_sub_classification', '-')}\n"
        f"📊 Status: {effective_status}\n"
        f"💰 Price: {asset.get('purchase_price', '-')} {asset.get('currency', '')}\n"
        f"🔢 Qty: {asset.get('quantity', '-')}\n"
        f"👤 Responsible person: {assignment.get('responsible_person') or '-'}\n"
        f"🏢 Department: {assignment.get('department') or '-'}\n"
        f"📍 City: {assignment.get('city') or '-'}\n"
        f"📅 Assignment date: {assignment_date}"
    )


async def send_asset_card(update: Update, asset_tag: str):
    asset = get_asset(asset_tag)

    if not asset:
        await update.message.reply_text(
            f"Asset {asset_tag} was not found.",
            reply_markup=main_keyboard,
        )
        return

    message = format_asset(asset)
    url = f"{API_URL}/view/{asset_tag}"

    inline_keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔍 Open asset card", url=url)]]
    )

    await update.message.reply_text(message, reply_markup=inline_keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    person = get_authorized_person(update)
    if person:
        await update.message.reply_text(
            f"Welcome back, {inventory_app.get_person_display_name(person)}. Choose an action below.",
            reply_markup=main_keyboard,
        )
        return

    await update.message.reply_text(
        "Scanventory\n\nPlease authorize first: tap 'Share phone number'.",
        reply_markup=auth_keyboard,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "1. Press 'Scan QR'\n"
        "2. Telegram will open the Mini App\n"
        "3. Scan the QR code\n"
        "4. The bot will show the asset card"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard)


def get_authorized_person(update: Update):
    telegram_user = update.effective_user
    if not telegram_user:
        return None
    person = inventory_app.find_person_by_telegram_user_id(telegram_user.id)
    if person and inventory_app.is_person_active(person):
        return person
    return None


def format_person_assets(person: dict) -> str:
    return inventory_app.format_person_assets_message(person)


async def reply_long_text(update: Update, text: str, reply_markup=None, max_length: int = 3500):
    lines = text.splitlines()
    chunks = []
    current = ""
    for line in lines:
        addition = line if not current else f"\n{line}"
        if len(current) + len(addition) > max_length:
            if current:
                chunks.append(current)
            current = line
        else:
            current += addition
    if current:
        chunks.append(current)
    if not chunks:
        chunks = [text]

    for index, chunk in enumerate(chunks):
        await update.message.reply_text(chunk, reply_markup=reply_markup if index == len(chunks) - 1 else None)


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    telegram_user = update.effective_user
    if not contact or not telegram_user or contact.user_id != telegram_user.id:
        await update.message.reply_text(
            "Please share your own phone number using the Telegram button.",
            reply_markup=auth_keyboard,
        )
        return

    person = inventory_app.find_person_by_phone(contact.phone_number)
    if not person:
        await update.message.reply_text(
            "Phone number was not found in the employee directory. Please contact the administrator.",
            reply_markup=auth_keyboard,
        )
        return
    if not inventory_app.is_person_active(person):
        await update.message.reply_text(
            "Your employee profile is inactive. Please contact the administrator.",
            reply_markup=auth_keyboard,
        )
        return

    inventory_app.save_person_telegram_identity(person["person_id"], telegram_user.to_dict(), contact.phone_number)
    await update.message.reply_text(
        f"Authorization successful. Welcome, {inventory_app.get_person_display_name(person)}.",
        reply_markup=main_keyboard,
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    person = get_authorized_person(update)

    if text == "Enter code":
        if not person:
            await update.message.reply_text(
                "Please authorize first: tap 'Share phone number'.",
                reply_markup=auth_keyboard,
            )
            return
        await update.message.reply_text(
            "Enter or paste the asset code, for example:\nHELP-UKR-0015",
            reply_markup=main_keyboard,
        )
        return

    if text == "Help":
        await help_command(update, context)
        return

    if not person:
        await update.message.reply_text(
            "Please authorize first: tap 'Share phone number'.",
            reply_markup=auth_keyboard,
        )
        return

    if text == "My assets":
        await reply_long_text(update, format_person_assets(person), reply_markup=main_keyboard)
        return

    await send_asset_card(update, text)


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw_data = update.message.web_app_data.data
        data = json.loads(raw_data)
        asset_tag = (data.get("asset_tag") or "").strip()

        if not asset_tag:
            await update.message.reply_text(
                "Could not read the asset code from Mini App.",
                reply_markup=main_keyboard,
            )
            return

        if not get_authorized_person(update):
            await update.message.reply_text(
                "Please authorize first: tap 'Share phone number'.",
                reply_markup=auth_keyboard,
            )
            return

        await send_asset_card(update, asset_tag)

    except Exception as exc:
        await update.message.reply_text(
            f"QR processing error:\n{exc}",
            reply_markup=main_keyboard,
        )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
