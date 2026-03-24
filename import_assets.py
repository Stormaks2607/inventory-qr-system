import math
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


client = create_client(SUPABASE_URL, SUPABASE_KEY)

FILE_PATH = "Inventory List_example_08.12.2025.xlsx"
SHEET_NAME = "Standard Asset List Format"


def clean_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def safe_int(value, default=1):
    if pd.isna(value):
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def safe_float(value):
    if pd.isna(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def load_excel():
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=7)

    df = df.rename(columns={
        "Asset Tag No. / Inventory Code\n(new standardised system)": "asset_tag_number",
        "Previous inventory code\n(if applicable)": "inventory_code_old",
        "Asset Classification": "asset_classification",
        "Asset Sub Classification": "asset_sub_classification",
        "Item Description": "item_description",
        "Brand / Make ": "brand_make",
        "Model": "model",
        "Serial/ Chassis No.": "serial_chassis_number",
        "Quantity": "quantity",
        "Date (Year) of Purchase": "date_of_purchase",
        "Purchase price": "purchase_price",
        "Currency": "currency",
        "Current Status\n(functionality)": "current_status",
        "Remarks": "remarks",
    })

    if "asset_tag_number" not in df.columns:
        raise ValueError("Не найдена колонка asset_tag_number. Проверь структуру Excel.")

    df = df[df["asset_tag_number"].notna()].copy()
    return df


def to_asset_record(row):
    asset_tag = clean_value(row.get("asset_tag_number"))
    if not asset_tag:
        return None

    inventory_code_old = clean_value(row.get("inventory_code_old"))

    record = {
        "asset_tag_number": asset_tag,
        "inventory_code": inventory_code_old or asset_tag,
        "asset_classification": clean_value(row.get("asset_classification")),
        "asset_sub_classification": clean_value(row.get("asset_sub_classification")),
        "item_description": clean_value(row.get("item_description")),
        "brand_make": clean_value(row.get("brand_make")),
        "model": clean_value(row.get("model")),
        "serial_chassis_number": clean_value(row.get("serial_chassis_number")),
        "quantity": safe_int(row.get("quantity"), default=1),
        "purchase_price": safe_float(row.get("purchase_price")),
        "currency": clean_value(row.get("currency")),
        "current_status": clean_value(row.get("current_status")),
        "remarks": clean_value(row.get("remarks")),
    }

    purchase_raw = clean_value(row.get("date_of_purchase"))
    if purchase_raw:
        purchase_str = str(purchase_raw).strip()
        # В файле формат вида 09-2021, PostgreSQL date так не примет.
        # Пока сохраняем только как remarks-дополнение, а date_placed_in_service не заполняем.
        if record["remarks"]:
            record["remarks"] = f"{record['remarks']} | Purchase period: {purchase_str}"
        else:
            record["remarks"] = f"Purchase period: {purchase_str}"

    return record


def asset_exists(asset_tag_number):
    resp = (
        client.table("assets")
        .select("asset_id")
        .eq("asset_tag_number", asset_tag_number)
        .limit(1)
        .execute()
    )
    return len(resp.data) > 0


def main():
    df = load_excel()
    inserted = 0
    skipped = 0
    errors = 0

    for _, row in df.iterrows():
        try:
            record = to_asset_record(row)
            if not record:
                skipped += 1
                continue

            if asset_exists(record["asset_tag_number"]):
                print(f"SKIP exists: {record['asset_tag_number']}")
                skipped += 1
                continue

            client.table("assets").insert(record).execute()
            print(f"OK: {record['asset_tag_number']}")
            inserted += 1

        except Exception as e:
            print(f"ERROR: {row.get('asset_tag_number')} -> {e}")
            errors += 1

    print("\n=== RESULT ===")
    print(f"Inserted: {inserted}")
    print(f"Skipped:  {skipped}")
    print(f"Errors:   {errors}")


if __name__ == "__main__":
    main()
