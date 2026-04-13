from typing import Optional
import json
import os

import requests
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from supabase import Client, create_client


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_BASE_URL = "https://inventory-qr-system.onrender.com"

app = FastAPI(title="Asset API", version="1.0.0")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
templates = Jinja2Templates(directory="templates")


def get_current_assignment(asset_id: int) -> Optional[dict]:
    assignment_response = (
        supabase.table("asset_assignments")
        .select("*")
        .eq("asset_id", asset_id)
        .is_("return_date", "null")
        .order("assignment_date", desc=True)
        .limit(1)
        .execute()
    )

    if not assignment_response.data:
        return None

    assignment = assignment_response.data[0]
    person = None
    location = None

    person_id = assignment.get("person_id")
    if person_id:
        person_response = (
            supabase.table("persons")
            .select("*")
            .eq("person_id", person_id)
            .limit(1)
            .execute()
        )
        if person_response.data:
            person = person_response.data[0]

    location_id = assignment.get("location_id")
    if location_id:
        location_response = (
            supabase.table("locations")
            .select("*")
            .eq("location_id", location_id)
            .limit(1)
            .execute()
        )
        if location_response.data:
            location = location_response.data[0]

    return {
        "assignment_id": assignment.get("assignment_id"),
        "assignment_date": assignment.get("assignment_date"),
        "status": assignment.get("status"),
        "notes": assignment.get("notes"),
        "responsible_person": (
            person.get("name_eng")
            or person.get("name")
            or person.get("full_name")
            if person
            else None
        ),
        "department": (
            (person.get("department") if person else None)
            or (location.get("department") if location else None)
        ),
        "city": location.get("city") if location else None,
        "location_name": location.get("name") if location else None,
    }


def get_asset_by_tag(asset_tag: str) -> Optional[dict]:
    response = (
        supabase.table("assets")
        .select("*")
        .eq("asset_tag_number", asset_tag)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None

    asset = response.data[0]
    asset["current_assignment"] = get_current_assignment(asset["asset_id"])
    return asset


def format_asset_message(asset: dict) -> str:
    assignment = asset.get("current_assignment") or {}
    effective_status = assignment.get("status") or asset.get("current_status") or "-"

    return (
        f"Asset: {asset.get('asset_tag_number', '-')}\n"
        f"Description: {asset.get('item_description', '-')}\n"
        f"Brand: {asset.get('brand_make', '-')}\n"
        f"Model: {asset.get('model', '-')}\n"
        f"Classification: {asset.get('asset_classification', '-')} / "
        f"{asset.get('asset_sub_classification', '-')}\n"
        f"Status: {effective_status}\n"
        f"Price: {asset.get('purchase_price', '-')} {asset.get('currency', '')}\n"
        f"Qty: {asset.get('quantity', '-')}\n"
        f"Responsible person: {assignment.get('responsible_person') or '-'}\n"
        f"Department: {assignment.get('department') or '-'}\n"
        f"City: {assignment.get('city') or '-'}"
    )


def send_telegram_message(chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json=payload,
        timeout=15,
    )


MAIN_KEYBOARD = {
    "keyboard": [
        [
            {"text": "Scan QR", "web_app": {"url": f"{PUBLIC_BASE_URL}/miniapp"}},
            {"text": "Enter code"},
        ],
        [{"text": "Help"}],
    ],
    "resize_keyboard": True,
}


@app.get("/")
def root():
    return {"status": "ok", "message": "Inventory system is running"}


@app.get("/asset/{asset_tag}")
def read_asset(asset_tag: str):
    asset = get_asset_by_tag(asset_tag.strip())
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


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
    try:
        print("UPDATE:", update)

        if "message" not in update:
            return {"ok": True}

        message = update["message"]
        chat_id = message["chat"]["id"]
        text = ""

        if "web_app_data" in message and message["web_app_data"].get("data"):
            raw_data = message["web_app_data"]["data"]
            try:
                payload = json.loads(raw_data)
                text = (payload.get("asset_tag") or "").strip()
            except Exception:
                text = raw_data.strip()
        elif message.get("text"):
            text = message["text"].strip()

        if not text:
            send_telegram_message(
                chat_id,
                "Send the asset code or use the button below.",
                reply_markup=MAIN_KEYBOARD,
            )
            return {"ok": True}

        if text == "/start":
            send_telegram_message(
                chat_id,
                (
                    "Welcome! This bot helps you find an asset by tag, "
                    "view a short card, and open the web card."
                ),
                reply_markup=MAIN_KEYBOARD,
            )
            return {"ok": True}

        if text == "Enter code":
            send_telegram_message(
                chat_id,
                "Enter the asset code, for example: HELP-UKR-0015",
            )
            return {"ok": True}

        if text == "Help":
            send_telegram_message(
                chat_id,
                "Use 'Scan QR' or enter the asset code manually.",
            )
            return {"ok": True}

        asset = get_asset_by_tag(text)
        if not asset:
            send_telegram_message(chat_id, f"Asset {text} was not found.")
            return {"ok": True}

        message_text = format_asset_message(asset)
        url = f"{PUBLIC_BASE_URL}/view/{text}"

        send_telegram_message(
            chat_id,
            message_text,
            reply_markup={
                "inline_keyboard": [
                    [{"text": "Open asset card", "url": url}]
                ]
            },
        )

        return {"ok": True}

    except Exception as exc:
        print("WEBHOOK ERROR:", exc)
        return {"ok": False, "error": str(exc)}
