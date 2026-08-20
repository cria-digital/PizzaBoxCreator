from app.db import repositories as repo


def test_client_create_normalizes_phone(db):
    client = repo.client_create(db, "Pizzaria A", "(11) 98888-7777")
    assert client["phone"] == "11988887777"


def test_client_get_by_phone_normalizes_query(db):
    repo.client_create(db, "Pizzaria A", "(11) 98888-7777")
    found = repo.client_get_by_phone(db, "11988887777")
    assert found is not None
    assert found["name"] == "Pizzaria A"


def test_client_get_by_phone_missing(db):
    assert repo.client_get_by_phone(db, "11900000000") is None


def test_client_upsert_updates_existing(db):
    repo.client_create(db, "Pizzaria A", "11988887777")
    updated = repo.client_upsert(db, "Pizzaria A Nova", "11988887777", instagram="@nova")
    assert updated["name"] == "Pizzaria A Nova"
    assert updated["instagram"] == "@nova"
    assert len(repo.client_list(db)) == 1


def test_order_create_with_quantidade(db, sample_client, sample_template):
    order = repo.order_create(
        db, sample_client["id"], sample_template["id"], {}, quantidade=1500
    )
    assert order["quantidade"] == 1500
    assert order["status"] == "draft"


def test_order_create_without_quantidade_defaults_to_none(db, sample_client, sample_template):
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    assert order["quantidade"] is None


def test_order_update_quantidade(db, sample_client, sample_template):
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    updated = repo.order_update_quantidade(db, order["id"], 2000)
    assert updated["quantidade"] == 2000


def test_order_get_active_for_client_excludes_finished(db, sample_client, sample_template):
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})

    active = repo.order_get_active_for_client(db, sample_client["id"])
    assert active["id"] == order["id"]

    repo.order_update_status(db, order["id"], "delivered")
    assert repo.order_get_active_for_client(db, sample_client["id"]) is None


def test_order_get_active_for_client_none_when_no_orders(db, sample_client):
    assert repo.order_get_active_for_client(db, sample_client["id"]) is None


def test_wa_message_claim_is_atomic(db):
    assert repo.wa_message_claim(db, "wamid.ABC") is True
    assert repo.wa_message_claim(db, "wamid.ABC") is False


def test_wa_message_set_order(db, sample_client, sample_template):
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    repo.wa_message_claim(db, "wamid.XYZ")
    repo.wa_message_set_order(db, "wamid.XYZ", order["id"])

    from sqlalchemy import text
    row = db.execute(
        text("SELECT order_id FROM whatsapp_messages WHERE wamid = :wamid"), {"wamid": "wamid.XYZ"}
    ).mappings().fetchone()
    assert row["order_id"] == order["id"]
