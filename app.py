from typing import Optional
import base64
import csv
import io
import secrets
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
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
BRANDING_SETTINGS_PATH = os.path.join("private_docs", "company_branding.json")
BRANDING_UPLOAD_DIR = os.path.join("private_docs", "branding")
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
BRANDING_SUPABASE_TABLE = "organization_branding"
DEFAULT_BRANDING_TENANT_KEY = "default"
ASSET_STATUS_OPTIONS = [
    ("functional", "Функціонуючий / Functional"),
    ("non-functional", "Не функціонуючий / Non-functional"),
    ("lost", "Втрачений / Lost"),
    ("disposed", "Списаний / Disposed"),
]

app = FastAPI(title="Asset API", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=ADMIN_SESSION_SECRET)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
templates = Jinja2Templates(directory="templates")


def get_default_branding_settings() -> dict:
    return {
        "company_name": "Your Company",
        "report_title": "Asset Assignment Statement",
        "report_subtitle": "Official summary of all assets currently assigned to the employee at the time of printing.",
        "report_theme": "classic",
        "primary_color": "#0f6c5c",
        "accent_color": "#f4fbf8",
        "footer_note": "Internal use only",
        "issuer_label": "Issued by",
        "issuer_signature_label": "Name, role, and signature",
        "receiver_label": "Received by employee",
        "receiver_signature_label": "Employee signature",
        "logo_path": "",
    }


def sanitize_tenant_key(value: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "-"
        for character in (value or "").strip()
    )
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed or DEFAULT_BRANDING_TENANT_KEY


def get_current_tenant_key(request: Request) -> str:
    return sanitize_tenant_key(request.session.get("admin_tenant_key") or DEFAULT_BRANDING_TENANT_KEY)


def get_legacy_tenant_key(request: Request) -> str:
    return sanitize_tenant_key(request.session.get("admin_username") or DEFAULT_BRANDING_TENANT_KEY)


def get_branding_settings_path(tenant_key: str) -> str:
    safe_tenant_key = sanitize_tenant_key(tenant_key)
    return os.path.join("private_docs", f"company_branding_{safe_tenant_key}.json")


def get_branding_upload_dir(tenant_key: str) -> str:
    safe_tenant_key = sanitize_tenant_key(tenant_key)
    return os.path.join(BRANDING_UPLOAD_DIR, safe_tenant_key)


def ensure_branding_storage() -> None:
    os.makedirs(os.path.dirname(BRANDING_SETTINGS_PATH), exist_ok=True)
    os.makedirs(BRANDING_UPLOAD_DIR, exist_ok=True)


def load_branding_settings_from_supabase(tenant_key: str) -> Optional[dict]:
    try:
        response = (
            supabase.table(BRANDING_SUPABASE_TABLE)
            .select("*")
            .eq("tenant_key", tenant_key)
            .limit(1)
            .execute()
        )
    except Exception:
        return None

    if not response.data:
        return None

    settings = get_default_branding_settings()
    settings.update(
        {
            key: value
            for key, value in response.data[0].items()
            if key in settings and value is not None
        }
    )
    return settings


def load_branding_settings_from_file(tenant_key: str) -> dict:
    ensure_branding_storage()
    settings_path = get_branding_settings_path(tenant_key)
    settings = get_default_branding_settings()
    if os.path.exists(settings_path):
        with open(settings_path, "r", encoding="utf-8") as file:
            saved = json.load(file)
        settings.update({key: value for key, value in saved.items() if key in settings})
    elif tenant_key == "default" and os.path.exists(BRANDING_SETTINGS_PATH):
        with open(BRANDING_SETTINGS_PATH, "r", encoding="utf-8") as file:
            saved = json.load(file)
        settings.update({key: value for key, value in saved.items() if key in settings})
    return settings


def load_branding_settings(tenant_key: str) -> tuple[dict, str]:
    settings = load_branding_settings_from_supabase(tenant_key)
    if settings is not None:
        return settings, "supabase"
    return load_branding_settings_from_file(tenant_key), "local"


def branding_matches_defaults(settings: dict) -> bool:
    defaults = get_default_branding_settings()
    return all(settings.get(key) == value for key, value in defaults.items())


def resolve_branding_for_request(request: Request) -> tuple[str, dict, str]:
    tenant_key = get_current_tenant_key(request)
    branding, branding_storage = load_branding_settings(tenant_key)
    if not branding_matches_defaults(branding):
        return tenant_key, branding, branding_storage

    legacy_tenant_key = get_legacy_tenant_key(request)
    if legacy_tenant_key != tenant_key:
        legacy_branding, legacy_storage = load_branding_settings(legacy_tenant_key)
        if not branding_matches_defaults(legacy_branding):
            return tenant_key, legacy_branding, legacy_storage

    return tenant_key, branding, branding_storage


def save_branding_settings_to_supabase(tenant_key: str, settings: dict) -> bool:
    payload = {"tenant_key": tenant_key, **settings}
    try:
        supabase.table(BRANDING_SUPABASE_TABLE).upsert(payload).execute()
        return True
    except Exception:
        return False


def save_branding_settings_to_file(tenant_key: str, settings: dict) -> None:
    ensure_branding_storage()
    settings_path = get_branding_settings_path(tenant_key)
    with open(settings_path, "w", encoding="utf-8") as file:
        json.dump(settings, file, ensure_ascii=False, indent=2)


def save_branding_settings(tenant_key: str, settings: dict) -> str:
    if save_branding_settings_to_supabase(tenant_key, settings):
        save_branding_settings_to_file(tenant_key, settings)
        return "supabase"

    save_branding_settings_to_file(tenant_key, settings)
    return "local"


def get_branding_logo_url(settings: dict) -> Optional[str]:
    logo_path = settings.get("logo_path") or ""
    if not logo_path:
        return None
    if logo_path.startswith("data:image/"):
        return logo_path
    return "/admin/branding/logo"


def save_branding_logo(tenant_key: str, logo_file: UploadFile, current_logo_path: str) -> str:
    ensure_branding_storage()
    upload_dir = get_branding_upload_dir(tenant_key)
    os.makedirs(upload_dir, exist_ok=True)
    filename = logo_file.filename or ""
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_LOGO_EXTENSIONS:
        raise ValueError("Logo must be a PNG, JPG, JPEG, or WEBP file.")

    safe_name = f"brand-logo{extension}"
    target_path = os.path.join(upload_dir, safe_name)

    file_bytes = logo_file.file.read()
    if not file_bytes:
        raise ValueError("Uploaded logo file is empty.")

    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(extension, "application/octet-stream")
    encoded = base64.b64encode(file_bytes).decode("ascii")
    logo_data_url = f"data:{mime_type};base64,{encoded}"

    if current_logo_path and not current_logo_path.startswith("data:image/") and current_logo_path != target_path and os.path.exists(current_logo_path):
        os.remove(current_logo_path)

    return logo_data_url


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


def normalize_asset_tag(value: str) -> str:
    return " ".join((value or "").strip().upper().split())


def validate_asset_tag_format(asset_tag_number: str) -> Optional[str]:
    if not asset_tag_number:
        return "Asset tag/Inventory No. is required."

    if not re.fullmatch(r"[A-Z0-9](?:[A-Z0-9/\- ]*[A-Z0-9])?", asset_tag_number):
        return "Asset tag/Inventory No. may only contain letters, digits, spaces, hyphens, and slashes."

    if not any(character.isdigit() for character in asset_tag_number):
        return "Asset tag/Inventory No. must contain at least one numeric part."

    return None


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


def get_person_display_name(person: dict) -> str:
    return (
        person.get("name_eng")
        or person.get("name")
        or person.get("full_name")
        or f"Person #{person.get('person_id')}"
    )


def get_person_report_name(person: dict) -> str:
    local_name = (person.get("name") or person.get("full_name") or "").strip()
    english_name = (person.get("name_eng") or "").strip()

    if local_name and english_name and local_name.casefold() != english_name.casefold():
        return f"{local_name} / {english_name}"

    return english_name or local_name or f"Person #{person.get('person_id')}"


def get_person_by_id(person_id: int) -> Optional[dict]:
    response = (
        supabase.table("persons")
        .select("*")
        .eq("person_id", person_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


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


def get_asset_form_values(asset: Optional[dict] = None) -> dict:
    asset = asset or {}
    return {
        "asset_tag_number": asset.get("asset_tag_number") or suggest_next_asset_tag(),
        "item_description": asset.get("item_description") or "",
        "brand_make": asset.get("brand_make") or "",
        "model": asset.get("model") or "",
        "asset_classification": asset.get("asset_classification") or "",
        "asset_sub_classification": asset.get("asset_sub_classification") or "",
        "quantity": asset.get("quantity") or "",
        "purchase_price": asset.get("purchase_price") or "",
        "currency": asset.get("currency") or "",
        "serial_number": asset.get("serial_number") or "",
        "current_status": asset.get("current_status") or "",
        "remarks": asset.get("remarks") or "",
    }


def list_lookup_values(table_name: str, column_name: str, fallback: Optional[list[str]] = None) -> list[str]:
    fallback = fallback or []
    try:
        response = (
            supabase.table(table_name)
            .select(column_name)
            .order(column_name)
            .execute()
        )
    except Exception:
        return fallback

    values = []
    for row in response.data or []:
        value = (row.get(column_name) or "").strip()
        if value and value not in values:
            values.append(value)
    return values or fallback


def list_distinct_asset_field_values(field_name: str) -> list[str]:
    try:
        response = supabase.table("assets").select(field_name).execute()
    except Exception:
        return []

    values = []
    for row in response.data or []:
        value = (row.get(field_name) or "").strip()
        if value and value not in values:
            values.append(value)
    return sorted(values)


def get_asset_create_options() -> dict:
    classifications = list_lookup_values(
        "asset_classifications",
        "classification_name",
        fallback=list_distinct_asset_field_values("asset_classification"),
    )
    sub_classifications = list_lookup_values(
        "asset_sub_classifications",
        "sub_classification_name",
        fallback=list_distinct_asset_field_values("asset_sub_classification"),
    )

    currencies = []
    for table_name, column_name in [
        ("currencies", "currency_code"),
        ("currencies", "code"),
        ("asset_currencies", "currency_code"),
        ("asset_currencies", "code"),
        ("currency", "currency_code"),
        ("currency", "code"),
    ]:
        currencies = list_lookup_values(table_name, column_name)
        if currencies:
            break

    if not currencies:
        currencies = list_distinct_asset_field_values("currency")

    return {
        "status_options": ASSET_STATUS_OPTIONS,
        "classification_options": classifications,
        "sub_classification_options": sub_classifications,
        "currency_options": currencies,
    }


def asset_tag_exists(asset_tag_number: str) -> bool:
    try:
        response = (
            supabase.table("assets")
            .select("asset_id")
            .eq("asset_tag_number", asset_tag_number)
            .limit(1)
            .execute()
        )
    except Exception:
        return False

    return bool(response.data)


def get_asset_tag_standard() -> dict:
    try:
        response = supabase.table("assets").select("asset_tag_number").execute()
    except Exception:
        return {"prefix": "", "width": 0, "example": "", "suggested_next": ""}

    sequence_map: dict[str, dict[str, int]] = {}
    for row in response.data or []:
        asset_tag = normalize_asset_tag(row.get("asset_tag_number") or "")
        match = re.match(r"^(.*?)(\d+)$", asset_tag)
        if not match:
            continue

        prefix = match.group(1)
        number = int(match.group(2))
        width = len(match.group(2))
        sequence = sequence_map.setdefault(prefix, {"count": 0, "max_number": 0, "width": width})
        sequence["count"] += 1
        if number > sequence["max_number"]:
            sequence["max_number"] = number
            sequence["width"] = width

    if not sequence_map:
        return {"prefix": "", "width": 0, "example": "", "suggested_next": ""}

    best_prefix, best_sequence = max(
        sequence_map.items(),
        key=lambda item: (item[1]["count"], item[1]["max_number"], item[0]),
    )
    next_number = best_sequence["max_number"] + 1
    width = best_sequence["width"]
    return {
        "prefix": best_prefix,
        "width": width,
        "example": f"{best_prefix}{'0' * max(width - 1, 0)}1" if width else "",
        "suggested_next": f"{best_prefix}{str(next_number).zfill(width)}" if width else "",
    }


def suggest_next_asset_tag() -> str:
    return get_asset_tag_standard().get("suggested_next") or ""


def get_asset_tag_warning(asset_tag_number: str, standard: Optional[dict] = None) -> str:
    asset_tag_number = normalize_asset_tag(asset_tag_number)
    standard = standard or get_asset_tag_standard()
    prefix = standard.get("prefix") or ""
    width = standard.get("width") or 0

    if not asset_tag_number or not prefix or not width:
        return ""

    match = re.match(r"^(.*?)(\d+)$", asset_tag_number)
    if not match:
        return "This inventory number does not follow the numbering pattern currently used in the database."

    current_prefix = match.group(1)
    current_width = len(match.group(2))
    if current_prefix != prefix or current_width != width:
        return "This inventory number differs from the numbering pattern currently used in the database."

    return ""


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


def search_people_with_assets(query: str = "", show_all: bool = False) -> list[dict]:
    assets = list_assets()
    people = list_people()
    assignments_by_person: dict[int, list[dict]] = {}

    for asset in assets:
        assignment = asset.get("current_assignment") or {}
        person_id = assignment.get("person_id")
        if person_id:
            assignments_by_person.setdefault(person_id, []).append(asset)

    rows: list[dict] = []
    normalized_query = query.strip().lower()

    for person in people:
        person_id = person.get("person_id")
        assigned_assets = assignments_by_person.get(person_id, [])
        row = {
            "person_id": person_id,
            "display_name": get_person_display_name(person),
            "department": person.get("department") or "-",
            "assigned_count": len(assigned_assets),
            "assets": assigned_assets,
        }

        if not show_all and row["assigned_count"] == 0:
            continue

        if normalized_query:
            haystack = " ".join(
                [
                    str(row["display_name"]),
                    str(person.get("department") or ""),
                    str(person.get("name") or ""),
                    str(person.get("name_eng") or ""),
                    str(person.get("full_name") or ""),
                ]
            ).lower()
            if normalized_query not in haystack:
                continue

        rows.append(row)

    rows.sort(key=lambda item: (-item["assigned_count"], item["display_name"]))
    return rows


def get_assets_for_person(person_id: int) -> list[dict]:
    return [
        asset
        for asset in list_assets()
        if (asset.get("current_assignment") or {}).get("person_id") == person_id
    ]


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


def summarize_assets_by_field(assets: list[dict], field_name: str, empty_label: str) -> list[dict]:
    counts: dict[str, int] = {}

    for asset in assets:
        assignment = asset.get("current_assignment") or {}
        label = assignment.get(field_name) or empty_label
        counts[label] = counts.get(label, 0) + 1

    return [
        {"label": key, "count": value}
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_assignment_audit_rows(assets: list[dict]) -> list[dict]:
    rows: list[dict] = []

    for asset in assets:
        assignment = asset.get("current_assignment") or {}
        rows.append(
            {
                "asset_tag_number": asset.get("asset_tag_number") or "",
                "item_description": asset.get("item_description") or "",
                "brand_make": asset.get("brand_make") or "",
                "model": asset.get("model") or "",
                "effective_status": asset.get("effective_status") or "",
                "current_status": asset.get("current_status") or "",
                "responsible_person": assignment.get("responsible_person") or "",
                "department": assignment.get("department") or "",
                "city": assignment.get("city") or "",
                "location_name": assignment.get("location_name") or "",
                "assignment_date": assignment.get("assignment_date") or "",
                "assignment_status": assignment.get("status") or "",
                "assignment_notes": assignment.get("notes") or "",
            }
        )

    return rows


def csv_response(filename: str, fieldnames: list[str], rows: list[dict]) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


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
    request.session["admin_username"] = input_username
    request.session["admin_tenant_key"] = DEFAULT_BRANDING_TENANT_KEY
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
            "flash": pop_flash(request),
            "active_page": "assets",
            "page_title": "Admin Assets",
            "admin_username": request.session.get("admin_username"),
        },
    )


@app.get("/admin/assets/new", response_class=HTMLResponse)
def admin_asset_new(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    asset_tag_standard = get_asset_tag_standard()
    return templates.TemplateResponse(
        request=request,
        name="admin_asset_create.html",
        context={
            "asset_form": get_asset_form_values(),
            **get_asset_create_options(),
            "asset_tag_standard": asset_tag_standard,
            "asset_tag_warning": "",
            "flash": pop_flash(request),
            "active_page": "assets",
            "page_title": "New Asset",
            "admin_username": request.session.get("admin_username"),
        },
    )


@app.post("/admin/assets/new")
def admin_asset_create(
    request: Request,
    asset_tag_number: str = Form(""),
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
    confirm_nonstandard_asset_tag: str = Form(""),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    asset_tag_standard = get_asset_tag_standard()
    asset_form = {
        "asset_tag_number": normalize_asset_tag(asset_tag_number),
        "item_description": item_description.strip(),
        "brand_make": brand_make.strip(),
        "model": model.strip(),
        "asset_classification": asset_classification.strip(),
        "asset_sub_classification": asset_sub_classification.strip(),
        "quantity": quantity.strip(),
        "purchase_price": purchase_price.strip(),
        "currency": currency.strip(),
        "serial_number": serial_number.strip(),
        "current_status": current_status.strip(),
        "remarks": remarks.strip(),
    }

    format_error = validate_asset_tag_format(asset_form["asset_tag_number"])
    if format_error:
        return templates.TemplateResponse(
            request=request,
            name="admin_asset_create.html",
            context={
                "asset_form": asset_form,
                **get_asset_create_options(),
                "asset_tag_standard": asset_tag_standard,
                "asset_tag_warning": "",
                "flash": {"level": "error", "message": format_error},
                "active_page": "assets",
                "page_title": "New Asset",
                "admin_username": request.session.get("admin_username"),
            },
            status_code=400,
        )

    asset_tag_warning = get_asset_tag_warning(asset_form["asset_tag_number"], asset_tag_standard)
    if asset_tag_warning and confirm_nonstandard_asset_tag != "yes":
        return templates.TemplateResponse(
            request=request,
            name="admin_asset_create.html",
            context={
                "asset_form": asset_form,
                **get_asset_create_options(),
                "asset_tag_standard": asset_tag_standard,
                "asset_tag_warning": asset_tag_warning,
                "flash": {"level": "error", "message": "Please confirm saving this non-standard inventory number."},
                "active_page": "assets",
                "page_title": "New Asset",
                "admin_username": request.session.get("admin_username"),
            },
            status_code=400,
        )

    if asset_tag_exists(asset_form["asset_tag_number"]):
        return templates.TemplateResponse(
            request=request,
            name="admin_asset_create.html",
            context={
                "asset_form": asset_form,
                **get_asset_create_options(),
                "asset_tag_standard": asset_tag_standard,
                "asset_tag_warning": asset_tag_warning,
                "flash": {"level": "error", "message": f"Asset tag/Inventory No. '{asset_form['asset_tag_number']}' already exists."},
                "active_page": "assets",
                "page_title": "New Asset",
                "admin_username": request.session.get("admin_username"),
            },
            status_code=400,
        )

    try:
        insert_data = {
            "asset_tag_number": asset_form["asset_tag_number"],
            "item_description": asset_form["item_description"] or None,
            "brand_make": asset_form["brand_make"] or None,
            "model": asset_form["model"] or None,
            "asset_classification": asset_form["asset_classification"] or None,
            "asset_sub_classification": asset_form["asset_sub_classification"] or None,
            "quantity": parse_int_field(asset_form["quantity"]),
            "purchase_price": parse_float_field(asset_form["purchase_price"]),
            "currency": asset_form["currency"] or None,
            "serial_number": asset_form["serial_number"] or None,
            "current_status": asset_form["current_status"] or None,
            "remarks": asset_form["remarks"] or None,
        }
    except ValueError:
        return templates.TemplateResponse(
            request=request,
            name="admin_asset_create.html",
            context={
                "asset_form": asset_form,
                **get_asset_create_options(),
                "asset_tag_standard": asset_tag_standard,
                "asset_tag_warning": asset_tag_warning,
                "flash": {"level": "error", "message": "Quantity must be an integer and purchase price must be a number."},
                "active_page": "assets",
                "page_title": "New Asset",
                "admin_username": request.session.get("admin_username"),
            },
            status_code=400,
        )

    try:
        response = (
            supabase.table("assets")
            .insert(insert_data)
            .execute()
        )
    except Exception:
        return templates.TemplateResponse(
            request=request,
            name="admin_asset_create.html",
            context={
                "asset_form": asset_form,
                **get_asset_create_options(),
                "asset_tag_standard": asset_tag_standard,
                "asset_tag_warning": asset_tag_warning,
                "flash": {"level": "error", "message": "Asset could not be created. Check whether the asset tag already exists."},
                "active_page": "assets",
                "page_title": "New Asset",
                "admin_username": request.session.get("admin_username"),
            },
            status_code=400,
        )

    created_asset = (response.data or [{}])[0]
    created_asset_id = created_asset.get("asset_id")
    if not created_asset_id:
        created_asset = get_asset_by_tag(asset_form["asset_tag_number"]) or {}
        created_asset_id = created_asset.get("asset_id")

    if not created_asset_id:
        set_flash(request, "success", f"Asset {asset_form['asset_tag_number']} was created.")
        return RedirectResponse(url="/admin/assets", status_code=303)

    set_flash(request, "success", f"Asset {asset_form['asset_tag_number']} was created.")
    return RedirectResponse(url=f"/admin/assets/{created_asset_id}", status_code=303)


@app.get("/admin/people", response_class=HTMLResponse)
def admin_people(request: Request, q: str = "", show_all: bool = False):
    redirect = require_admin(request)
    if redirect:
        return redirect

    people = search_people_with_assets(q, show_all=show_all)

    return templates.TemplateResponse(
        request=request,
        name="admin_people.html",
        context={
            "people": people,
            "query": q,
            "show_all": show_all,
            "active_page": "people",
            "page_title": "People",
            "admin_username": request.session.get("admin_username"),
        },
    )


@app.get("/admin/people/{person_id}", response_class=HTMLResponse)
def admin_person_detail(request: Request, person_id: int):
    redirect = require_admin(request)
    if redirect:
        return redirect

    person = get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    assigned_assets = get_assets_for_person(person_id)
    display_name = get_person_display_name(person)
    report_display_name = get_person_report_name(person)
    printed_at = datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%d.%m.%Y")
    tenant_key, branding, branding_storage = resolve_branding_for_request(request)

    return templates.TemplateResponse(
        request=request,
        name="admin_person_detail.html",
        context={
            "person": person,
            "display_name": display_name,
            "report_display_name": report_display_name,
            "assigned_assets": assigned_assets,
            "printed_at": printed_at,
            "branding": branding,
            "branding_storage": branding_storage,
            "tenant_key": tenant_key,
            "branding_logo_url": get_branding_logo_url(branding),
            "active_page": "people",
            "page_title": display_name,
            "admin_username": request.session.get("admin_username"),
        },
    )


@app.get("/admin/branding/logo")
def admin_branding_logo(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    _, branding, _ = resolve_branding_for_request(request)
    logo_path = branding.get("logo_path") or ""
    if not logo_path or logo_path.startswith("data:image/") or not os.path.exists(logo_path):
        raise HTTPException(status_code=404, detail="Logo not found")

    return FileResponse(logo_path)


@app.get("/admin/branding", response_class=HTMLResponse)
def admin_branding(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    tenant_key, branding, branding_storage = resolve_branding_for_request(request)
    return templates.TemplateResponse(
        request=request,
        name="admin_branding.html",
        context={
            "branding": branding,
            "branding_storage": branding_storage,
            "tenant_key": tenant_key,
            "branding_logo_url": get_branding_logo_url(branding),
            "flash": pop_flash(request),
            "active_page": "branding",
            "page_title": "Branding",
            "admin_username": request.session.get("admin_username"),
        },
    )


@app.post("/admin/branding")
def admin_branding_save(
    request: Request,
    company_name: str = Form(""),
    report_title: str = Form(""),
    report_subtitle: str = Form(""),
    report_theme: str = Form("classic"),
    primary_color: str = Form(""),
    accent_color: str = Form(""),
    footer_note: str = Form(""),
    issuer_label: str = Form(""),
    issuer_signature_label: str = Form(""),
    receiver_label: str = Form(""),
    receiver_signature_label: str = Form(""),
    logo_file: Optional[UploadFile] = File(None),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    tenant_key, branding, _ = resolve_branding_for_request(request)
    branding.update(
        {
            "company_name": company_name.strip() or get_default_branding_settings()["company_name"],
            "report_title": report_title.strip() or get_default_branding_settings()["report_title"],
            "report_subtitle": report_subtitle.strip() or get_default_branding_settings()["report_subtitle"],
            "report_theme": report_theme.strip() if report_theme.strip() in {"classic", "corporate", "compact", "help_standard"} else get_default_branding_settings()["report_theme"],
            "primary_color": primary_color.strip() or get_default_branding_settings()["primary_color"],
            "accent_color": accent_color.strip() or get_default_branding_settings()["accent_color"],
            "footer_note": footer_note.strip() or get_default_branding_settings()["footer_note"],
            "issuer_label": issuer_label.strip() or get_default_branding_settings()["issuer_label"],
            "issuer_signature_label": issuer_signature_label.strip() or get_default_branding_settings()["issuer_signature_label"],
            "receiver_label": receiver_label.strip() or get_default_branding_settings()["receiver_label"],
            "receiver_signature_label": receiver_signature_label.strip() or get_default_branding_settings()["receiver_signature_label"],
        }
    )

    try:
        if logo_file and (logo_file.filename or "").strip():
            branding["logo_path"] = save_branding_logo(tenant_key, logo_file, branding.get("logo_path") or "")
    except ValueError as error:
        set_flash(request, "error", str(error))
        return RedirectResponse(url="/admin/branding", status_code=303)

    storage_backend = save_branding_settings(tenant_key, branding)
    set_flash(request, "success", f"Branding settings were updated for tenant '{tenant_key}' using {storage_backend} storage.")
    return RedirectResponse(url="/admin/branding", status_code=303)


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


@app.get("/admin/reports/export/{report_name}")
def admin_reports_export(request: Request, report_name: str):
    redirect = require_admin(request)
    if redirect:
        return redirect

    assets = list_assets()

    if report_name == "cities":
        rows = summarize_assets_by_field(assets, "city", "Unknown")
        return csv_response(
            "assets-by-city.csv",
            ["label", "count"],
            [{"label": row["label"], "count": row["count"]} for row in rows],
        )

    if report_name == "departments":
        rows = summarize_assets_by_field(assets, "department", "Unknown")
        return csv_response(
            "assets-by-department.csv",
            ["label", "count"],
            [{"label": row["label"], "count": row["count"]} for row in rows],
        )

    if report_name == "people":
        rows = summarize_assets_by_field(assets, "responsible_person", "Unassigned")
        return csv_response(
            "assets-by-responsible-person.csv",
            ["label", "count"],
            [{"label": row["label"], "count": row["count"]} for row in rows],
        )

    if report_name == "assignments":
        return csv_response(
            "assignment-audit.csv",
            [
                "asset_tag_number",
                "item_description",
                "brand_make",
                "model",
                "effective_status",
                "current_status",
                "responsible_person",
                "department",
                "city",
                "location_name",
                "assignment_date",
                "assignment_status",
                "assignment_notes",
            ],
            build_assignment_audit_rows(assets),
        )

    raise HTTPException(status_code=404, detail="Report not found")


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
