from typing import Optional
import secrets
import json
import os

import requests
from dotenv import load_dotenv
from fastapi import Body, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
from supabase import Client, create_client


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_BASE_URL = "https://inventory-qr-system.onrender.com"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")
ADMIN_SESSION_SECRET = os.getenv("ADMIN_SESSION_SECRET", "replace-this-session-secret")

app = FastAPI(title="Asset API", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=ADMIN_SESSION_SECRET)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
templates = Jinja2Templates(directory="templates")


def is_admin_authenticated(request: Request) -> bool:
    return request.session.get("admin_authenticated") is True


def normalize_credential(value: str) -> str:
    normalized = (value or "").strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1]
    return normalized


def parse_int_field(value: str) -> Optional[int]:
    normalized = (value or "").strip()
    if not normalized:
        return None
    return int(normalized)


def parse_float_field(value: str) -> Optional[float]:
    normalized = (value or "").strip().replace(",", ".")
    if not normalized:
        return None
    return float(normalized)


def require_admin(request: Request) -> Optional[RedirectResponse]:
    if is_admin_authenticated(request):
        return None

    login_url = app.url_path_for("admin_login")
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"

    redirect_url = f"{login_url}?next={next_path}"
    return RedirectResponse(url=redirect_url, status_code=303)


def set_flash(request: Request, level: str, message: str) -> None:
    request.session["admin_flash"] = {"level": level, "message": message}


def pop_flash(request: Request) -> Optional[dict]:
    return request.session.pop("admin_flash", None)


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
        "person_id": assignment.get("person_id"),
        "location_id": assignment.get("location_id"),
        "assignment_date": assignment.get("assignment_date"),
        "return_date": assignment.get("return_date"),
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


def enrich_assignment(assignment: dict) -> dict:
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
        "person_id": assignment.get("person_id"),
        "location_id": assignment.get("location_id"),
        "assignment_date": assignment.get("assignment_date"),
        "return_date": assignment.get("return_date"),
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


def get_asset_by_id(asset_id: int) -> Optional[dict]:
    response = (
        supabase.table("assets")
        .select("*")
        .eq("asset_id", asset_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None

    asset = response.data[0]
    asset["current_assignment"] = get_current_assignment(asset["asset_id"])
    asset["effective_status"] = get_effective_status(asset)
    return asset


def get_assignment_history(asset_id: int, limit: int = 20) -> list[dict]:
    response = (
        supabase.table("asset_assignments")
        .select("*")
        .eq("asset_id", asset_id)
        .order("assignment_date", desc=True)
        .limit(limit)
        .execute()
    )

    assignments = response.data or []
    return [enrich_assignment(assignment) for assignment in assignments]


def list_people() -> list[dict]:
    response = (
        supabase.table("persons")
        .select("*")
        .order("name_eng")
        .execute()
    )
    return response.data or []


def list_locations() -> list[dict]:
    response = (
        supabase.table("locations")
        .select("*")
        .order("city")
        .execute()
    )
    return response.data or []


def close_current_assignments(asset_id: int, return_date: Optional[str]) -> None:
    current_assignments = (
        supabase.table("asset_assignments")
        .select("assignment_id")
        .eq("asset_id", asset_id)
        .is_("return_date", "null")
        .execute()
    )

    for row in current_assignments.data or []:
        (
            supabase.table("asset_assignments")
            .update({"return_date": return_date})
            .eq("assignment_id", row["assignment_id"])
            .execute()
        )


def get_assignment_form_context(asset: dict) -> dict:
    current_assignment = asset.get("current_assignment") or {}
    return {
        "people": list_people(),
        "locations": list_locations(),
        "assignment_form": {
            "person_id": current_assignment.get("person_id") or "",
            "location_id": current_assignment.get("location_id") or "",
            "assignment_date": current_assignment.get("assignment_date") or "",
            "status": current_assignment.get("status") or asset.get("current_status") or "",
            "notes": current_assignment.get("notes") or "",
        },
    }


def get_effective_status(asset: dict) -> str:
    assignment = asset.get("current_assignment") or {}
    return assignment.get("status") or asset.get("current_status") or "-"


def list_assets(limit: Optional[int] = None, batch_size: int = 500) -> list[dict]:
    assets: list[dict] = []
    start = 0

    while True:
        query = (
            supabase.table("assets")
            .select("*")
            .order("asset_tag_number")
            .range(start, start + batch_size - 1)
        )
        if limit is not None:
            remaining = limit - len(assets)
            if remaining <= 0:
                break
            query = query.limit(min(batch_size, remaining))

        response = query.execute()
        batch = response.data or []
        if not batch:
            break

        assets.extend(batch)

        if limit is not None and len(assets) >= limit:
            assets = assets[:limit]
            break

        if len(batch) < batch_size:
            break

        start += len(batch)

    for asset in assets:
        asset["current_assignment"] = get_current_assignment(asset["asset_id"])
        asset["effective_status"] = get_effective_status(asset)
    return assets


def asset_matches_query(asset: dict, query: str) -> bool:
    if not query:
        return True

    assignment = asset.get("current_assignment") or {}
    haystack = [
        asset.get("asset_tag_number"),
        asset.get("item_description"),
        asset.get("brand_make"),
        asset.get("model"),
        asset.get("asset_classification"),
        asset.get("asset_sub_classification"),
        asset.get("effective_status"),
        assignment.get("responsible_person"),
        assignment.get("department"),
        assignment.get("city"),
    ]

    normalized_query = query.lower()
    return any(
        normalized_query in str(value).lower()
        for value in haystack
        if value
    )


def field_contains(value: Optional[str], query: str) -> bool:
    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return True
    return normalized_query in str(value or "").lower()


def asset_matches_filters(asset: dict, filters: dict[str, str]) -> bool:
    assignment = asset.get("current_assignment") or {}
    return (
        field_contains(asset.get("asset_tag_number"), filters.get("asset_tag", ""))
        and field_contains(asset.get("item_description"), filters.get("description", ""))
        and field_contains(asset.get("effective_status"), filters.get("status", ""))
        and field_contains(assignment.get("responsible_person"), filters.get("person", ""))
        and field_contains(assignment.get("department"), filters.get("department", ""))
        and field_contains(assignment.get("city"), filters.get("city", ""))
    )


def build_asset_summary(assets: list[dict]) -> dict:
    assigned_count = 0
    unassigned_count = 0
    lost_count = 0
    city_map: dict[str, int] = {}
    department_map: dict[str, int] = {}
    person_map: dict[str, int] = {}

    for asset in assets:
        assignment = asset.get("current_assignment") or {}
        status = (asset.get("effective_status") or "").upper()
        city = assignment.get("city") or "Unknown"
        department = assignment.get("department") or "Unknown"
        person = assignment.get("responsible_person") or "Unassigned"

        if assignment:
            assigned_count += 1
        else:
            unassigned_count += 1

        if status == "LOST":
            lost_count += 1

        city_map[city] = city_map.get(city, 0) + 1
        department_map[department] = department_map.get(department, 0) + 1
        person_map[person] = person_map.get(person, 0) + 1

    def top_items(data: dict[str, int], limit: int = 8) -> list[dict]:
        return [
            {"label": key, "count": value}
            for key, value in sorted(data.items(), key=lambda item: (-item[1], item[0]))[:limit]
        ]

    return {
        "total_assets": len(assets),
        "assigned_assets": assigned_count,
        "unassigned_assets": unassigned_count,
        "lost_assets": lost_count,
        "top_cities": top_items(city_map),
        "top_departments": top_items(department_map),
        "top_people": top_items(person_map),
    }


def format_asset_message(asset: dict) -> str:
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


@app.get("/admin/login", response_class=HTMLResponse, name="admin_login")
def admin_login(request: Request, next: str = "/admin"):
    if is_admin_authenticated(request):
        return RedirectResponse(url=next or "/admin", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={
            "error": None,
            "next_url": next or "/admin",
        },
    )


@app.post("/admin/login", response_class=HTMLResponse)
def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/admin"),
):
    input_username = normalize_credential(username)
    input_password = normalize_credential(password)
    expected_username = normalize_credential(ADMIN_USERNAME)
    expected_password = normalize_credential(ADMIN_PASSWORD)

    valid_username = secrets.compare_digest(input_username, expected_username)
    valid_password = secrets.compare_digest(input_password, expected_password)

    if not (valid_username and valid_password):
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={
                "error": "Invalid username or password.",
                "next_url": next or "/admin",
            },
            status_code=401,
        )

    request.session["admin_authenticated"] = True
    request.session["admin_username"] = username
    return RedirectResponse(url=next or "/admin", status_code=303)


@app.get("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    assets = list_assets()
    summary = build_asset_summary(assets)

    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "summary": summary,
            "active_page": "dashboard",
            "page_title": "Admin Dashboard",
            "admin_username": request.session.get("admin_username"),
        },
    )


@app.get("/admin/assets", response_class=HTMLResponse)
def admin_assets(
    request: Request,
    q: str = "",
    asset_tag: str = "",
    description: str = "",
    status: str = "",
    person: str = "",
    department: str = "",
    city: str = "",
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    assets = list_assets()
    filters = {
        "asset_tag": asset_tag.strip(),
        "description": description.strip(),
        "status": status.strip(),
        "person": person.strip(),
        "department": department.strip(),
        "city": city.strip(),
    }
    filtered_assets = [
        asset
        for asset in assets
        if asset_matches_query(asset, q.strip()) and asset_matches_filters(asset, filters)
    ]

    return templates.TemplateResponse(
        request=request,
        name="admin_assets.html",
        context={
            "assets": filtered_assets,
            "query": q,
            "filters": filters,
            "total_found": len(filtered_assets),
            "active_page": "assets",
            "page_title": "Admin Assets",
            "admin_username": request.session.get("admin_username"),
        },
    )


@app.get("/admin/assets/{asset_id}", response_class=HTMLResponse)
def admin_asset_detail(request: Request, asset_id: int):
    redirect = require_admin(request)
    if redirect:
        return redirect

    asset = get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    assignment_history = get_assignment_history(asset_id)

    return templates.TemplateResponse(
        request=request,
        name="admin_asset_detail.html",
        context={
            "asset": asset,
            "assignment_history": assignment_history,
            "flash": pop_flash(request),
            "active_page": "assets",
            "page_title": f"Asset {asset.get('asset_tag_number')}",
            "admin_username": request.session.get("admin_username"),
            **get_assignment_form_context(asset),
        },
    )


@app.post("/admin/assets/{asset_id}/edit")
def admin_asset_edit(
    request: Request,
    asset_id: int,
    item_description: str = Form(""),
    brand_make: str = Form(""),
    model: str = Form(""),
    asset_classification: str = Form(""),
    asset_sub_classification: str = Form(""),
    quantity: str = Form(""),
    purchase_price: str = Form(""),
    currency: str = Form(""),
    serial_number: str = Form(""),
    current_status: str = Form(""),
    remarks: str = Form(""),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    asset = get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        update_data = {
            "item_description": item_description.strip() or None,
            "brand_make": brand_make.strip() or None,
            "model": model.strip() or None,
            "asset_classification": asset_classification.strip() or None,
            "asset_sub_classification": asset_sub_classification.strip() or None,
            "quantity": parse_int_field(quantity),
            "purchase_price": parse_float_field(purchase_price),
            "currency": currency.strip() or None,
            "serial_number": serial_number.strip() or None,
            "current_status": current_status.strip() or None,
            "remarks": remarks.strip() or None,
        }
    except ValueError:
        set_flash(request, "error", "Quantity must be an integer and purchase price must be a number.")
        return RedirectResponse(url=f"/admin/assets/{asset_id}", status_code=303)

    (
        supabase.table("assets")
        .update(update_data)
        .eq("asset_id", asset_id)
        .execute()
    )

    set_flash(request, "success", "Asset details were updated.")
    return RedirectResponse(url=f"/admin/assets/{asset_id}", status_code=303)


@app.post("/admin/assets/{asset_id}/assignment")
def admin_asset_assignment_update(
    request: Request,
    asset_id: int,
    person_id: str = Form(""),
    location_id: str = Form(""),
    assignment_date: str = Form(""),
    status: str = Form(""),
    notes: str = Form(""),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    asset = get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    person_id = person_id.strip()
    location_id = location_id.strip()
    assignment_date = assignment_date.strip()
    status = status.strip()
    notes = notes.strip()

    if not assignment_date:
        set_flash(request, "error", "Assignment date is required.")
        return RedirectResponse(url=f"/admin/assets/{asset_id}", status_code=303)

    if bool(person_id) != bool(location_id):
        set_flash(request, "error", "Select both responsible person and location, or leave both empty to unassign.")
        return RedirectResponse(url=f"/admin/assets/{asset_id}", status_code=303)

    current_assignment = asset.get("current_assignment")

    if not person_id and not location_id:
        if current_assignment:
            close_current_assignments(asset_id, assignment_date)
            if status:
                supabase.table("assets").update({"current_status": status}).eq("asset_id", asset_id).execute()
            set_flash(request, "success", "Current assignment was closed and the asset is now unassigned.")
        else:
            if status:
                supabase.table("assets").update({"current_status": status}).eq("asset_id", asset_id).execute()
            set_flash(request, "success", "Asset is already unassigned.")
        return RedirectResponse(url=f"/admin/assets/{asset_id}", status_code=303)

    new_assignment = {
        "asset_id": asset_id,
        "person_id": int(person_id),
        "location_id": int(location_id),
        "assignment_date": assignment_date,
        "return_date": None,
        "status": status or None,
        "notes": notes or None,
    }

    if (
        current_assignment
        and current_assignment.get("person_id") == int(person_id)
        and current_assignment.get("location_id") == int(location_id)
    ):
        (
            supabase.table("asset_assignments")
            .update({
                "assignment_date": assignment_date,
                "status": status or None,
                "notes": notes or None,
            })
            .eq("assignment_id", current_assignment["assignment_id"])
            .execute()
        )
        if status:
            supabase.table("assets").update({"current_status": status}).eq("asset_id", asset_id).execute()
        set_flash(request, "success", "Current assignment was updated.")
        return RedirectResponse(url=f"/admin/assets/{asset_id}", status_code=303)

    close_current_assignments(asset_id, assignment_date)
    supabase.table("asset_assignments").insert(new_assignment).execute()
    if status:
        supabase.table("assets").update({"current_status": status}).eq("asset_id", asset_id).execute()
    set_flash(request, "success", "Assignment was updated.")
    return RedirectResponse(url=f"/admin/assets/{asset_id}", status_code=303)


@app.get("/admin/reports", response_class=HTMLResponse)
def admin_reports(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    assets = list_assets()
    summary = build_asset_summary(assets)

    return templates.TemplateResponse(
        request=request,
        name="admin_reports.html",
        context={
            "summary": summary,
            "active_page": "reports",
            "page_title": "Admin Reports",
            "admin_username": request.session.get("admin_username"),
        },
    )


@app.get("/admin/sync", response_class=HTMLResponse)
def admin_sync(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    sync_rules = [
        "Supabase is the operational working database.",
        "The Excel inventory file remains the official control file.",
        "Imports from Excel should go through controlled sync steps, not direct blind overwrite.",
        "Exports to Excel should preserve the official reporting structure.",
        "Before applying sync changes, the system should show a comparison preview.",
    ]

    return templates.TemplateResponse(
        request=request,
        name="admin_sync.html",
        context={
            "sync_rules": sync_rules,
            "excel_file_name": "Inventory List_example_08.12.2025.xlsx",
            "active_page": "sync",
            "page_title": "Admin Sync",
            "admin_username": request.session.get("admin_username"),
        },
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
                    [{"text": "🔍 Open asset card", "url": url}]
                ]
            },
        )

        return {"ok": True}

    except Exception as exc:
        print("WEBHOOK ERROR:", exc)
        return {"ok": False, "error": str(exc)}
