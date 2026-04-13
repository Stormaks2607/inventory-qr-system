import os
import re
import warnings
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client
from difflib import get_close_matches, SequenceMatcher

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

FILE_PATH = "Inventory List_example_08.12.2025.xlsx"
SHEET_NAME = "Standard Asset List Format"
OUTPUT_CSV = "person_matching_debug.csv"


def clean(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return str(value).strip()


def soft_normalize(value):
    """
    Мягкая нормализация только для диагностики:
    - trim
    - замена множественных пробелов на один
    - унификация апострофов/дефисов
    - без upper/lower
    """
    value = clean(value)
    if value is None:
        return None

    value = value.replace("’", "'").replace("`", "'").replace("–", "-").replace("—", "-")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def lower_key(value):
    value = soft_normalize(value)
    return value.lower() if value else None


def similarity(a, b):
    return round(SequenceMatcher(None, a, b).ratio() * 100, 1)


def load_excel_names():
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=7)

    recipient_col = "Name of Recipient"
    if recipient_col not in df.columns:
        raise ValueError(f"Column not found: {recipient_col}")

    names = []
    for v in df[recipient_col].dropna().tolist():
        v = clean(v)
        if not v:
            continue
        if v.lower() in ["warehouse", "administration"]:
            continue
        names.append(v)

    # сохранить порядок, убрать дубли
    unique_names = list(dict.fromkeys(names))
    return unique_names


def load_db_persons():
    rows = supabase.table("persons").select("person_id,name_eng,name").execute().data

    persons = []
    for row in rows:
        name_eng = clean(row.get("name_eng"))
        if not name_eng:
            continue

        persons.append({
            "person_id": row["person_id"],
            "name_eng": name_eng,
            "name": clean(row.get("name")),
            "soft": soft_normalize(name_eng),
            "lower": lower_key(name_eng),
        })
    return persons


def main():
    excel_names = load_excel_names()
    persons = load_db_persons()

    exact_map = {p["name_eng"]: p for p in persons}
    lower_map = {p["lower"]: p for p in persons if p["lower"]}
    db_names = [p["name_eng"] for p in persons]
    db_soft_names = [p["soft"] for p in persons if p["soft"]]

    results = []

    exact_count = 0
    normalized_count = 0
    not_found_count = 0

    print(f"Excel unique names: {len(excel_names)}")
    print(f"DB persons with name_eng: {len(persons)}")
    print("-" * 80)

    for excel_name in excel_names:
        excel_soft = soft_normalize(excel_name)
        excel_lower = lower_key(excel_name)

        status = None
        matched_person_id = None
        matched_name_eng = None
        matched_name_local = None
        best_guess = None
        best_score = None

        # 1. exact
        if excel_name in exact_map:
            p = exact_map[excel_name]
            status = "exact"
            matched_person_id = p["person_id"]
            matched_name_eng = p["name_eng"]
            matched_name_local = p["name"]
            exact_count += 1

        # 2. case/space normalized exact
        elif excel_lower in lower_map:
            p = lower_map[excel_lower]
            status = "normalized_exact"
            matched_person_id = p["person_id"]
            matched_name_eng = p["name_eng"]
            matched_name_local = p["name"]
            normalized_count += 1

        # 3. best fuzzy guess for review
        else:
            status = "not_found"
            not_found_count += 1

            candidates = get_close_matches(excel_soft, db_soft_names, n=1, cutoff=0.6)
            if candidates:
                candidate_soft = candidates[0]
                # find original record
                for p in persons:
                    if p["soft"] == candidate_soft:
                        best_guess = p["name_eng"]
                        best_score = similarity(excel_soft, candidate_soft)
                        break

        results.append({
            "excel_name": excel_name,
            "excel_name_soft": excel_soft,
            "status": status,
            "matched_person_id": matched_person_id,
            "matched_name_eng": matched_name_eng,
            "matched_name_local": matched_name_local,
            "best_guess_name_eng": best_guess,
            "best_guess_score": best_score,
        })

    result_df = pd.DataFrame(results)
    result_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"Exact matches: {exact_count}")
    print(f"Normalized exact matches: {normalized_count}")
    print(f"Not found: {not_found_count}")
    print(f"Saved report: {OUTPUT_CSV}")
    print("-" * 80)

    not_found_df = result_df[result_df["status"] == "not_found"].copy()

    if not not_found_df.empty:
        print("Top unresolved names:")
        preview_cols = ["excel_name", "best_guess_name_eng", "best_guess_score"]
        print(not_found_df[preview_cols].head(30).to_string(index=False))
    else:
        print("All names matched.")


if __name__ == "__main__":
    main()