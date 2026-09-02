RETIRED_MESSAGE = "Legacy import script is retired. Use the tenant-aware application import flow."
raise RuntimeError(RETIRED_MESSAGE)

import os
import re
import warnings
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FILE_PATH = "Inventory List_example_08.12.2025.xlsx"
SHEET_NAME = "Standard Asset List Format"


def clean(value):
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


def parse_date(value):
    value = clean(value)
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    value = str(value).strip()

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def limit_text(value, max_len, field_name="", asset_tag=""):
    value = clean(value)
    if value is None:
        return None

    value = str(value)
    if len(value) > max_len:
        print(
            f"WARNING: {field_name} too long for {asset_tag}. "
            f"Length={len(value)}, truncated to {max_len}"
        )
        return value[:max_len]

    return value


def normalize_classification(value):
    value = clean(value)
    if value is None:
        return None

    value = str(value).strip()
    value = value.replace("…", "")
    value = re.sub(r"\.+$", "", value)

    return value.strip()


def load_excel():
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=7)

    df = df.rename(columns={
        "Asset Tag No. / Inventory Code\n(new standardised system)": "asset_tag_number",
        "Previous inventory code\n(if applicable)": "previous_inventory_code",
        "Asset Classification": "asset_classification",
        "Asset Sub Classification": "asset_sub_classification",
        "Item Description": "item_description",
        "Brand / Make ": "brand_make",
        "Model": "model",
        "Serial/ Chassis No.": "serial_chassis_number",
        "Quantity": "quantity",
        "Location": "location_name",
        "Department ": "department_name",
        "Name of Recipient": "recipient_name",
        "Position of Recipient": "recipient_position",
        "Date (Year) of Purchase": "purchase_date_raw",
        "Purchase price": "purchase_price",
        "Currency": "currency",
        "Purchased to Project No.": "purchased_project_no",
        "Donor ": "donor_name",
        "Transferred to Project No.": "transferred_project_no",
        "Current Status\n(functionality)": "current_status",
        "Remarks": "remarks",
        "Last date of transfer": "last_transfer_date",
    })

    df = df[df["asset_tag_number"].notna()].copy()
    return df


def get_table_map(table_name, key_field, id_field):
    rows = supabase.table(table_name).select("*").execute().data
    result = {}
    for row in rows:
        key = row.get(key_field)
        if isinstance(key, str):
            key = key.strip()
        if key:
            result[key] = row[id_field]
    return result


def asset_exists(asset_tag_number):
    resp = (
        supabase.table("assets")
        .select("asset_id")
        .eq("asset_tag_number", asset_tag_number)
        .limit(1)
        .execute()
    )
    return resp.data[0]["asset_id"] if resp.data else None


def get_asset_project(asset_id, project_id):
    result = (
        supabase.table("asset_projects")
        .select("*")
        .eq("asset_id", asset_id)
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def insert_or_update_asset_project(
    asset_id,
    project_id,
    donor_id,
    is_current,
    transfer_date,
    transfer_reason,
    condition_at_transfer,
    mode_label,
    asset_tag,
    project_number,
    counters,
):
    existing = get_asset_project(asset_id, project_id)

    if not existing:
        supabase.table("asset_projects").insert({
            "asset_id": asset_id,
            "project_id": project_id,
            "donor_id": donor_id,
            "assignment_date": None,
            "is_current": is_current,
            "transfer_date": transfer_date,
            "transfer_reason": transfer_reason,
            "condition_at_transfer": condition_at_transfer,
        }).execute()

        counters["inserted_asset_projects"] += 1
        print(f"ASSET_PROJECT INSERTED ({mode_label}): {asset_tag} -> {project_number}")
        return

    update_data = {}
    updated = False

    # donor backfill
    if existing.get("donor_id") is None and donor_id is not None:
        update_data["donor_id"] = donor_id
        updated = True

    # optionally fill missing transfer info
    if existing.get("transfer_date") is None and transfer_date is not None:
        update_data["transfer_date"] = transfer_date
        updated = True

    if existing.get("transfer_reason") is None and transfer_reason is not None:
        update_data["transfer_reason"] = transfer_reason
        updated = True

    if existing.get("condition_at_transfer") is None and condition_at_transfer is not None:
        update_data["condition_at_transfer"] = condition_at_transfer
        updated = True

    # if transferred project is the current one, can safely promote is_current
    if is_current and existing.get("is_current") is not True:
        update_data["is_current"] = True
        updated = True

    if updated:
        (
            supabase.table("asset_projects")
            .update(update_data)
            .eq("asset_project_id", existing["asset_project_id"])
            .execute()
        )
        counters["updated_asset_projects"] += 1
        print(f"ASSET_PROJECT UPDATED ({mode_label}): {asset_tag} -> {project_number}")
    else:
        counters["skipped_asset_projects"] += 1
        print(f"ASSET_PROJECT SKIPPED ({mode_label}): {asset_tag} -> {project_number}")


def main():
    df = load_excel()

    donor_map = get_table_map("donors", "donor_name", "donor_id")
    project_map = get_table_map("projects", "project_number", "project_id")
    classification_map = get_table_map("asset_classifications", "classification_name", "classification_id")
    subclassification_map = get_table_map("asset_sub_classifications", "sub_classification_name", "sub_classification_id")

    counters = {
        "inserted_assets": 0,
        "skipped_assets": 0,
        "inserted_asset_projects": 0,
        "updated_asset_projects": 0,
        "skipped_asset_projects": 0,
        "missing_purchased_projects": 0,
        "missing_transferred_projects": 0,
        "missing_donors": 0,
    }

    for _, row in df.iterrows():
        asset_tag = clean(row.get("asset_tag_number"))
        if not asset_tag:
            continue

        remarks = clean(row.get("remarks"))
        purchase_raw = clean(row.get("purchase_date_raw"))
        if purchase_raw:
            extra = f"Purchase period: {purchase_raw}"
            remarks = f"{remarks} | {extra}" if remarks else extra

        location_name = clean(row.get("location_name"))
        department_name = clean(row.get("department_name"))
        recipient_name = clean(row.get("recipient_name"))
        recipient_position = clean(row.get("recipient_position"))

        extra_parts = []
        if location_name:
            extra_parts.append(f"Location: {location_name}")
        if department_name:
            extra_parts.append(f"Department: {department_name}")
        if recipient_name:
            extra_parts.append(f"Recipient: {recipient_name}")
        if recipient_position:
            extra_parts.append(f"Position: {recipient_position}")

        if extra_parts:
            extra_text = " | ".join(extra_parts)
            remarks = f"{remarks} | {extra_text}" if remarks else extra_text

        classification_name = normalize_classification(row.get("asset_classification"))
        subclassification_name = normalize_classification(row.get("asset_sub_classification"))
        donor_name = clean(row.get("donor_name"))

        if classification_name and classification_name not in classification_map:
            print(f"WARNING: classification not found in DB: {classification_name}")

        if subclassification_name and subclassification_name not in subclassification_map:
            print(f"WARNING: sub-classification not found in DB: {subclassification_name}")

        donor_id = donor_map.get(donor_name) if donor_name else None
        if donor_name and donor_id is None:
            print(f"WARNING: donor not found in DB: {donor_name}")
            counters["missing_donors"] += 1

        asset_data = {
            "asset_tag_number": asset_tag,
            "inventory_code": asset_tag,
            "asset_classification": limit_text(classification_name, 50, "asset_classification", asset_tag),
            "asset_sub_classification": limit_text(subclassification_name, 50, "asset_sub_classification", asset_tag),
            "item_description": clean(row.get("item_description")),
            "brand_make": limit_text(row.get("brand_make"), 100, "brand_make", asset_tag),
            "model": clean(row.get("model")),
            "serial_chassis_number": limit_text(row.get("serial_chassis_number"), 100, "serial_chassis_number", asset_tag),
            "quantity": safe_int(row.get("quantity"), default=1),
            "purchase_price": safe_float(row.get("purchase_price")),
            "currency": limit_text(row.get("currency"), 3, "currency", asset_tag),
            "current_status": limit_text(row.get("current_status"), 20, "current_status", asset_tag),
            "remarks": remarks,
        }

        asset_id = asset_exists(asset_tag)

        if not asset_id:
            inserted = supabase.table("assets").insert(asset_data).execute()
            asset_id = inserted.data[0]["asset_id"]
            counters["inserted_assets"] += 1
            print(f"ASSET INSERTED: {asset_tag}")
        else:
            counters["skipped_assets"] += 1
            print(f"ASSET SKIPPED: {asset_tag}")

        purchased_project_no = clean(row.get("purchased_project_no"))
        transferred_project_no = clean(row.get("transferred_project_no"))
        last_transfer_date = parse_date(row.get("last_transfer_date"))
        current_status = clean(row.get("current_status"))

        # purchased project
        if purchased_project_no:
            if purchased_project_no in project_map:
                project_id = project_map[purchased_project_no]

                insert_or_update_asset_project(
                    asset_id=asset_id,
                    project_id=project_id,
                    donor_id=donor_id,
                    is_current=(transferred_project_no is None),
                    transfer_date=None,
                    transfer_reason=None,
                    condition_at_transfer=current_status,
                    mode_label="purchased",
                    asset_tag=asset_tag,
                    project_number=purchased_project_no,
                    counters=counters,
                )
            else:
                print(f"WARNING: purchased project not found in DB: {purchased_project_no}")
                counters["missing_purchased_projects"] += 1

        # transferred project
        if transferred_project_no:
            if transferred_project_no in project_map:
                transferred_project_id = project_map[transferred_project_no]

                insert_or_update_asset_project(
                    asset_id=asset_id,
                    project_id=transferred_project_id,
                    donor_id=donor_id,
                    is_current=True,
                    transfer_date=last_transfer_date,
                    transfer_reason="Imported from Excel transfer data",
                    condition_at_transfer=current_status,
                    mode_label="transferred",
                    asset_tag=asset_tag,
                    project_number=transferred_project_no,
                    counters=counters,
                )
            else:
                print(f"WARNING: transferred project not found in DB: {transferred_project_no}")
                counters["missing_transferred_projects"] += 1

    print("\n=== RESULT ===")
    print(f"Inserted assets: {counters['inserted_assets']}")
    print(f"Skipped assets: {counters['skipped_assets']}")
    print(f"Inserted asset_projects: {counters['inserted_asset_projects']}")
    print(f"Updated asset_projects: {counters['updated_asset_projects']}")
    print(f"Skipped asset_projects: {counters['skipped_asset_projects']}")
    print(f"Missing purchased projects: {counters['missing_purchased_projects']}")
    print(f"Missing transferred projects: {counters['missing_transferred_projects']}")
    print(f"Missing donors: {counters['missing_donors']}")


if __name__ == "__main__":
    main()
