import asyncio
import json
from types import SimpleNamespace


TENANT_ONE = "00000000-0000-4000-8000-000000000001"
TENANT_TWO = "00000000-0000-4000-8000-000000000002"


class FakeResponse:
    def __init__(self, data=None, status_code=200):
        self.data = data or []
        self.status_code = status_code

    def json(self):
        return self.data


class MemoryQuery:
    def __init__(self, store, table_name, operations):
        self.store = store
        self.table_name = table_name
        self.operations = operations
        self.filters = []
        self.limit_value = None
        self.update_payload = None

    def select(self, *args, **kwargs):
        self.operations.append((self.table_name, "select", args, kwargs))
        return self

    def update(self, payload):
        self.update_payload = dict(payload)
        self.operations.append((self.table_name, "update", dict(payload)))
        return self

    def eq(self, field_name, value):
        self.filters.append((field_name, value))
        self.operations.append((self.table_name, "eq", field_name, value))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        rows = [
            dict(row)
            for row in self.store.get(self.table_name, [])
            if all(str(row.get(field)) == str(value) for field, value in self.filters)
        ]
        if self.update_payload is not None:
            for stored_row in self.store.get(self.table_name, []):
                if all(str(stored_row.get(field)) == str(value) for field, value in self.filters):
                    stored_row.update(self.update_payload)
            rows = [dict(row) for row in rows]
            for row in rows:
                row.update(self.update_payload)
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return FakeResponse(rows)


class MemorySupabase:
    def __init__(self, store):
        self.store = store
        self.operations = []

    def table(self, table_name):
        return MemoryQuery(self.store, table_name, self.operations)


def telegram_person(person_id, telegram_id, tenant_id):
    return {
        "person_id": person_id,
        "name_eng": f"Person {person_id}",
        "messenger_type": "telegram",
        "messenger_id": str(telegram_id),
        "tenant_id": tenant_id,
        "is_active": True,
    }


def telegram_update(telegram_id, *, text=None, web_app_data=None):
    message = {
        "chat": {"id": telegram_id},
        "from": {"id": telegram_id},
    }
    if text is not None:
        message["text"] = text
    if web_app_data is not None:
        message["web_app_data"] = {"data": json.dumps(web_app_data)}
    return {"message": message}


def install_webhook_identity(monkeypatch, app_module, person, asset_lookup):
    monkeypatch.setattr(app_module, "TELEGRAM_WEBHOOK_SECRET", "telegram-secret")
    monkeypatch.setattr(app_module, "find_person_by_telegram_user_id", lambda telegram_id: person)
    monkeypatch.setattr(
        app_module,
        "get_active_telegram_person_tenant_id",
        lambda candidate, **kwargs: candidate.get("tenant_id") if candidate else None,
    )
    monkeypatch.setattr(app_module, "get_asset_by_tag", asset_lookup)


def test_telegram_identity_resolves_unique_person_across_tenants(app_module, monkeypatch):
    tenant_one_person = telegram_person(1, 101, TENANT_ONE)
    tenant_two_person = telegram_person(2, 202, TENANT_TWO)
    fake = MemorySupabase(
        {
            "tenants": [
                {"tenant_id": TENANT_ONE, "status": "active"},
                {"tenant_id": TENANT_TWO, "status": "active"},
            ],
            "persons": [tenant_one_person, tenant_two_person],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake)

    resolved = app_module.find_person_by_telegram_user_id(202)

    assert resolved["person_id"] == 2
    person_filters = [operation for operation in fake.operations if operation[:2] == ("persons", "eq")]
    assert ("persons", "eq", "messenger_type", "telegram") in person_filters
    assert ("persons", "eq", "messenger_id", "202") in person_filters
    assert all(operation[2] != "tenant_id" for operation in person_filters)


def test_telegram_identity_fails_closed_when_mapping_is_ambiguous(app_module, monkeypatch):
    fake = MemorySupabase(
        {
            "tenants": [
                {"tenant_id": TENANT_ONE, "status": "active"},
                {"tenant_id": TENANT_TWO, "status": "active"},
            ],
            "persons": [
                telegram_person(1, 500, TENANT_ONE),
                telegram_person(2, 500, TENANT_TWO),
            ],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake)

    assert app_module.find_person_by_telegram_user_id(500) is None


def test_phone_onboarding_resolves_unique_tenant_person_and_scopes_write(app_module, monkeypatch):
    person = telegram_person(2, 0, TENANT_TWO)
    person.update({"messenger_id": None, "mobile_phone": "+380 50 123 45 67"})
    fake = MemorySupabase(
        {
            "tenants": [{"tenant_id": TENANT_TWO, "status": "active"}],
            "persons": [person],
        }
    )
    monkeypatch.setattr(app_module, "supabase", fake)

    resolved = app_module.find_person_by_phone("0501234567")
    saved = app_module.save_person_telegram_identity(
        resolved["person_id"],
        {"id": 202, "username": "tenant_two"},
        "+380501234567",
        tenant_id=resolved["tenant_id"],
    )

    assert saved is True
    assert person["messenger_id"] == "202"
    assert ("persons", "eq", "tenant_id", TENANT_TWO) in fake.operations


def test_trusted_tenant_two_webhook_uses_scoped_lookup_and_canonical_link(
    app_module,
    client,
    monkeypatch,
):
    person = telegram_person(2, 202, TENANT_TWO)
    lookups = []
    sent = []

    def asset_lookup(asset_tag, *, tenant_id=None):
        lookups.append((asset_tag, tenant_id))
        return {"asset_id": 22, "asset_tag_number": asset_tag, "item_description": "Tenant Two asset"}

    install_webhook_identity(monkeypatch, app_module, person, asset_lookup)
    monkeypatch.setattr(
        app_module,
        "send_telegram_message",
        lambda chat_id, text, reply_markup=None: sent.append((chat_id, text, reply_markup)),
    )

    response = client.post(
        "/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"},
        json=telegram_update(202, text="SHARED-TAG"),
    )

    assert response.status_code == 200
    assert lookups == [("SHARED-TAG", TENANT_TWO)]
    asset_url = sent[-1][2]["inline_keyboard"][0][0]["url"]
    assert asset_url.endswith(f"/t/{TENANT_TWO}/view/SHARED-TAG")


def test_tenant_two_identity_cannot_resolve_tenant_one_asset(app_module, client, monkeypatch):
    person = telegram_person(2, 202, TENANT_TWO)
    lookups = []
    sent = []

    def asset_lookup(asset_tag, *, tenant_id=None):
        lookups.append((asset_tag, tenant_id))
        return None

    install_webhook_identity(monkeypatch, app_module, person, asset_lookup)
    monkeypatch.setattr(
        app_module,
        "send_telegram_message",
        lambda chat_id, text, reply_markup=None: sent.append(text),
    )

    response = client.post(
        "/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"},
        json=telegram_update(202, text="TENANT-ONE-ASSET"),
    )

    assert response.status_code == 200
    assert lookups == [("TENANT-ONE-ASSET", TENANT_TWO)]
    assert sent[-1] == "Asset TENANT-ONE-ASSET was not found."


def test_miniapp_payload_cannot_override_trusted_tenant(app_module, client, monkeypatch):
    person = telegram_person(2, 202, TENANT_TWO)
    lookups = []

    def asset_lookup(asset_tag, *, tenant_id=None):
        lookups.append((asset_tag, tenant_id))
        return {"asset_id": 22, "asset_tag_number": asset_tag}

    install_webhook_identity(monkeypatch, app_module, person, asset_lookup)
    monkeypatch.setattr(app_module, "send_telegram_message", lambda *args, **kwargs: None)

    response = client.post(
        "/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"},
        json=telegram_update(
            202,
            web_app_data={"asset_tag": "TENANT-TWO-ASSET", "tenant_id": TENANT_ONE},
        ),
    )

    assert response.status_code == 200
    assert lookups == [("TENANT-TWO-ASSET", TENANT_TWO)]


def test_unmapped_telegram_identity_fails_closed(app_module, client, monkeypatch):
    monkeypatch.setattr(app_module, "TELEGRAM_WEBHOOK_SECRET", "telegram-secret")
    monkeypatch.setattr(app_module, "find_person_by_telegram_user_id", lambda telegram_id: None)
    monkeypatch.setattr(
        app_module,
        "get_asset_by_tag",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("asset lookup must not run")),
    )
    prompts = []
    monkeypatch.setattr(app_module, "send_telegram_auth_prompt", lambda chat_id: prompts.append(chat_id))

    response = client.post(
        "/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"},
        json=telegram_update(999, text="UNKNOWN-ASSET"),
    )

    assert response.status_code == 200
    assert prompts == [999]


def test_unverified_webhook_cannot_authorize_non_default_tenant(app_module, client, monkeypatch):
    person = telegram_person(2, 202, TENANT_TWO)
    monkeypatch.setattr(app_module, "TELEGRAM_WEBHOOK_SECRET", None)
    monkeypatch.setattr(app_module, "find_person_by_telegram_user_id", lambda telegram_id: person)
    monkeypatch.setattr(
        app_module,
        "get_active_telegram_person_tenant_id",
        lambda candidate, **kwargs: candidate.get("tenant_id") if candidate else None,
    )
    monkeypatch.setattr(
        app_module,
        "get_asset_by_tag",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("asset lookup must not run")),
    )
    prompts = []
    monkeypatch.setattr(app_module, "send_telegram_auth_prompt", lambda chat_id: prompts.append(chat_id))

    response = client.post("/webhook", json=telegram_update(202, text="TENANT-TWO-ASSET"))

    assert response.status_code == 200
    assert prompts == [202]


def test_invalid_webhook_secret_is_rejected_before_identity_lookup(app_module, client, monkeypatch):
    monkeypatch.setattr(app_module, "TELEGRAM_WEBHOOK_SECRET", "telegram-secret")
    monkeypatch.setattr(
        app_module,
        "find_person_by_telegram_user_id",
        lambda telegram_id: (_ for _ in ()).throw(AssertionError("identity lookup must not run")),
    )

    response = client.post(
        "/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json=telegram_update(202, text="TENANT-TWO-ASSET"),
    )

    assert response.status_code == 403


def test_legacy_tenant_one_webhook_still_works_without_secret(app_module, client, monkeypatch):
    person = telegram_person(1, 101, TENANT_ONE)
    lookups = []
    sent = []
    monkeypatch.setattr(app_module, "TELEGRAM_WEBHOOK_SECRET", None)
    monkeypatch.setattr(app_module, "find_person_by_telegram_user_id", lambda telegram_id: person)
    monkeypatch.setattr(
        app_module,
        "get_active_telegram_person_tenant_id",
        lambda candidate, **kwargs: candidate.get("tenant_id") if candidate else None,
    )
    monkeypatch.setattr(
        app_module,
        "get_asset_by_tag",
        lambda asset_tag, *, tenant_id=None: lookups.append((asset_tag, tenant_id))
        or {"asset_id": 1, "asset_tag_number": asset_tag},
    )
    monkeypatch.setattr(
        app_module,
        "send_telegram_message",
        lambda chat_id, text, reply_markup=None: sent.append(reply_markup),
    )

    response = client.post("/webhook", json=telegram_update(101, text="LEGACY-ASSET"))

    assert response.status_code == 200
    assert lookups == [("LEGACY-ASSET", TENANT_ONE)]
    assert sent[-1]["inline_keyboard"][0][0]["url"].endswith(
        f"/t/{TENANT_ONE}/view/LEGACY-ASSET"
    )


def test_signed_asset_list_token_binds_person_lookup_to_tenant(app_module, monkeypatch):
    person = telegram_person(2, 202, TENANT_TWO)
    monkeypatch.setattr(
        app_module,
        "get_active_telegram_person_tenant_id",
        lambda candidate, **kwargs: candidate.get("tenant_id") if candidate else None,
    )
    token = app_module.create_telegram_asset_list_token(person)
    decoded = app_module.get_telegram_asset_list_serializer().loads(token)
    lookups = []
    monkeypatch.setattr(app_module, "resolve_public_tenant_id", lambda tenant_id: tenant_id)
    monkeypatch.setattr(
        app_module,
        "get_person_by_id",
        lambda person_id, request=None, tenant_id=None: lookups.append((person_id, tenant_id)) or person,
    )

    assert decoded["tenant_id"] == TENANT_TWO
    assert app_module.load_telegram_asset_list_person(token) == person
    assert lookups == [(2, TENANT_TWO)]


def test_telegram_asset_message_scopes_person_assets_to_mapped_tenant(app_module, monkeypatch):
    person = telegram_person(2, 202, TENANT_TWO)
    lookups = []
    monkeypatch.setattr(
        app_module,
        "get_active_telegram_person_tenant_id",
        lambda candidate, **kwargs: candidate.get("tenant_id") if candidate else None,
    )
    monkeypatch.setattr(
        app_module,
        "get_assets_for_person",
        lambda person_id, request=None, tenant_id=None: lookups.append((person_id, tenant_id)) or [],
    )

    app_module.format_person_assets_message(person)

    assert lookups == [(2, TENANT_TWO)]


def test_legacy_tenant_one_asset_list_token_remains_compatible(app_module, monkeypatch):
    person = {
        "person_id": 1,
        "messenger_id": "101",
        "name_eng": "Legacy person",
        "is_active": True,
    }
    token = app_module.get_telegram_asset_list_serializer().dumps(
        {"person_id": 1, "messenger_id": "101"}
    )
    monkeypatch.setattr(app_module, "resolve_public_tenant_id", lambda tenant_id: tenant_id)
    monkeypatch.setattr(
        app_module,
        "get_person_by_id",
        lambda person_id, request=None, tenant_id=None: person,
    )

    assert app_module.load_telegram_asset_list_person(token) == person


def test_standalone_bot_uses_tenant_qualified_api_and_view_links(app_module, monkeypatch):
    import bot as bot_module

    person = telegram_person(2, 202, TENANT_TWO)
    requested_urls = []
    monkeypatch.setattr(
        bot_module.requests,
        "get",
        lambda url, timeout: requested_urls.append(url)
        or FakeResponse({"asset_id": 22, "asset_tag_number": "TENANT TWO/ASSET"}),
    )

    assert bot_module.get_asset("TENANT TWO/ASSET", TENANT_TWO)["asset_id"] == 22
    assert requested_urls[-1].endswith(f"/t/{TENANT_TWO}/asset/TENANT%20TWO%2FASSET")

    replies = []

    async def reply_text(text, reply_markup=None):
        replies.append((text, reply_markup))

    update = SimpleNamespace(message=SimpleNamespace(reply_text=reply_text))
    monkeypatch.setattr(
        app_module,
        "get_active_telegram_person_tenant_id",
        lambda candidate, **kwargs: TENANT_TWO,
    )
    monkeypatch.setattr(
        bot_module,
        "get_asset",
        lambda asset_tag, tenant_id: {"asset_id": 22, "asset_tag_number": asset_tag},
    )

    asyncio.run(bot_module.send_asset_card(update, "TENANT TWO/ASSET", person))

    button = replies[-1][1].inline_keyboard[0][0]
    assert button.url.endswith(f"/t/{TENANT_TWO}/view/TENANT%20TWO%2FASSET")
