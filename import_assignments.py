import os
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
DEFAULT_ASSIGNMENT_DATE = "2000-01-01"


def clean(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


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


def load_excel():
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=7)

    df = df.rename(columns={
        "Asset Tag No. / Inventory Code\n(new standardised system)": "asset_tag_number",
        "Location": "city",
        "Name of Recipient": "recipient_name",
        "Position of Recipient": "recipient_position",
        "Current Status\n(functionality)": "current_status",
        "Last date of transfer": "last_transfer_date",
        "Date (Year) of Purchase": "purchase_date_raw",
        "Remarks": "remarks",
    })

    df = df[df["asset_tag_number"].notna()].copy()
    return df


def get_asset_map():
    rows = supabase.table("assets").select("asset_id,asset_tag_number").execute().data
    result = {}
    for row in rows:
        asset_tag = clean(row.get("asset_tag_number"))
        if asset_tag:
            result[asset_tag] = row["asset_id"]
    return result


def get_person_map():
    rows = supabase.table("persons").select("*").execute().data
    result = {}

    for row in rows:
        name_eng = clean(row.get("name_eng"))
        if name_eng:
            result[name_eng] = row

    return result


def get_location_map():
    rows = supabase.table("locations").select("*").execute().data
    result = {}

    for row in rows:
        city = clean(row.get("city"))
        department = clean(row.get("department"))

        if city and department:
            result[(city, department)] = row

    return result


def assignment_exists(asset_id, person_id, location_id):
    result = (
        supabase.table("asset_assignments")
        .select("assignment_id")
        .eq("asset_id", asset_id)
        .eq("person_id", person_id)
        .eq("location_id", location_id)
        .is_("return_date", "null")
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


def close_existing_current_assignments(asset_id, new_assignment_date=None):
    result = (
        supabase.table("asset_assignments")
        .select("assignment_id")
        .eq("asset_id", asset_id)
        .is_("return_date", "null")
        .execute()
    )

    for row in result.data:
        (
            supabase.table("asset_assignments")
            .update({"return_date": new_assignment_date})
            .eq("assignment_id", row["assignment_id"])
            .execute()
        )


def is_system_person(name):
    if not name:
        return False
    return name.strip().lower() in ["warehouse", "administration"]


def build_assignment_date(row):
    transfer_date = parse_date(row.get("last_transfer_date"))
    if transfer_date:
        return transfer_date

    purchase_date = parse_date(row.get("purchase_date_raw"))
    if purchase_date:
        return purchase_date

    return DEFAULT_ASSIGNMENT_DATE


def main():
    df = load_excel()

    asset_map = get_asset_map()
    person_map = get_person_map()
    location_map = get_location_map()

    inserted = 0
    skipped = 0
    skipped_system_persons = 0
    not_found_assets = 0
    not_found_persons = 0
    not_found_locations = 0

    for _, row in df.iterrows():
        asset_tag = clean(row.get("asset_tag_number"))
        city = clean(row.get("city"))
        recipient_name = clean(row.get("recipient_name"))
        recipient_position = clean(row.get("recipient_position"))
        current_status = clean(row.get("current_status"))
        assignment_date = build_assignment_date(row)
        remarks = clean(row.get("remarks"))

        if not asset_tag:
            skipped += 1
            continue

        if not recipient_name:
            print(f"SKIPPED NO RECIPIENT: {asset_tag}")
            skipped += 1
            continue

        if is_system_person(recipient_name):
            print(f"SKIPPED SYSTEM PERSON: {asset_tag} -> {recipient_name}")
            skipped_system_persons += 1
            continue

        asset_id = asset_map.get(asset_tag)
        if not asset_id:
            print(f"ASSET NOT FOUND: {asset_tag}")
            not_found_assets += 1
            continue

        person = person_map.get(recipient_name)
        if not person:
            print(f"PERSON NOT FOUND: {recipient_name}")
            not_found_persons += 1
            continue

        person_id = person["person_id"]
        department = clean(person.get("department"))

        if not city or not department:
            print(
                f"LOCATION INPUT INCOMPLETE: "
                f"asset={asset_tag}, city={city}, department={department}"
            )
            not_found_locations += 1
            continue

        location = location_map.get((city, department))
        if not location:
            print(
                f"LOCATION NOT FOUND: "
                f"asset={asset_tag}, city={city}, department={department}"
            )
            not_found_locations += 1
            continue

        location_id = location["location_id"]

        if assignment_exists(asset_id, person_id, location_id):
            print(f"ASSIGNMENT SKIPPED: {asset_tag}")
            skipped += 1
            continue

        close_existing_current_assignments(asset_id, assignment_date)

        notes_parts = []
        if recipient_position:
            notes_parts.append(f"Position from Excel: {recipient_position}")
        if current_status:
            notes_parts.append(f"Asset status: {current_status}")
        if remarks:
            notes_parts.append(f"Remarks: {remarks}")

        notes = " | ".join(notes_parts) if notes_parts else None

        assignment_data = {
            "asset_id": asset_id,
            "person_id": person_id,
            "location_id": location_id,
            "assignment_date": assignment_date,
            "return_date": None,
            "status": current_status,
            "notes": notes,
        }

        supabase.table("asset_assignments").insert(assignment_data).execute()
        inserted += 1
        print(
            f"ASSIGNMENT INSERTED: "
            f"{asset_tag} -> {recipient_name} -> {city} / {department} | date={assignment_date}"
        )

    print("\n=== RESULT ===")
    print(f"Inserted assignments: {inserted}")
    print(f"Skipped assignments: {skipped}")
    print(f"Skipped system persons: {skipped_system_persons}")
    print(f"Assets not found: {not_found_assets}")
    print(f"Persons not found: {not_found_persons}")
    print(f"Locations not found: {not_found_locations}")


if __name__ == "__main__":
    main()