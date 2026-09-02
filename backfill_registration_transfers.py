import argparse
import json
from types import SimpleNamespace

from app import backfill_asset_registration_transfers
from data_access.tenant import normalize_tenant_uuid


def parse_args():
    parser = argparse.ArgumentParser(
        description="Dry-run or apply tenant-scoped durable asset registration transfers."
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Tenant UUID to inspect. The value is operator-controlled and never read from a workbook.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create proposed transfers. Without this flag the command is read-only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tenant_id = normalize_tenant_uuid(args.tenant_id)
    request = SimpleNamespace(
        session={
            "admin_authenticated": True,
            "admin_role": "admin",
            "admin_username": "registration-transfer-backfill",
            "tenant_id": tenant_id,
        }
    )
    result = backfill_asset_registration_transfers(
        request,
        apply=args.apply,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
