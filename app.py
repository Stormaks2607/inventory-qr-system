from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from supabase import create_client, Client
from dotenv import load_dotenv
import os



# =========================
# НАСТРОЙКИ
# =========================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # ОБЯЗАТЕЛЬНО новый, не тот что был на скрине!
templates = Jinja2Templates(directory="templates")
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
    return {"message": "Asset API is running"}


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
        "asset.html",
        {"request": request, "asset": asset}
    )
@app.get("/miniapp", response_class=HTMLResponse)
def miniapp(request: Request):
    return templates.TemplateResponse(
        "miniapp.html",
        {"request": request}
    )
@app.get("/")
def root():
    return {"status": "ok", "message": "Inventory system is running"}
