from __future__ import annotations


def test_clients_api_requires_login(api_client):
    r = api_client.get("/api/clients")
    assert r.status_code == 401


def test_create_client_validates_and_normalizes_fields(api_authed_client):
    r = api_authed_client.post(
        "/api/clients",
        json={"name": "  Pizzaria CRUD  ", "phone": "(11) 98888-7777", "instagram": "crudpizza"},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Pizzaria CRUD"
    assert data["phone"] == "11988887777"
    assert data["instagram"] == "@crudpizza"


def test_create_client_rejects_invalid_name_and_phone(api_authed_client):
    r = api_authed_client.post("/api/clients", json={"name": "A", "phone": "123"})

    assert r.status_code == 422


def test_get_client_by_id_and_phone(api_authed_client):
    created = api_authed_client.post(
        "/api/clients",
        json={"name": "Pizzaria Busca", "phone": "(11) 97777-6666"},
    ).json()

    by_id = api_authed_client.get(f"/api/clients/{created['id']}")
    by_phone = api_authed_client.get("/api/clients/by-phone/11977776666")
    legacy_by_phone = api_authed_client.get("/api/clients/(11)%2097777-6666")

    assert by_id.status_code == 200
    assert by_phone.status_code == 200
    assert legacy_by_phone.status_code == 200
    assert by_id.json()["id"] == created["id"]
    assert by_phone.json()["id"] == created["id"]
    assert legacy_by_phone.json()["id"] == created["id"]


def test_update_client_partial(api_authed_client):
    created = api_authed_client.post(
        "/api/clients",
        json={"name": "Pizzaria Antiga", "phone": "11911112222"},
    ).json()

    r = api_authed_client.patch(
        f"/api/clients/{created['id']}",
        json={"name": "Pizzaria Nova", "instagram": "nova"},
    )

    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Pizzaria Nova"
    assert data["phone"] == "11911112222"
    assert data["instagram"] == "@nova"


def test_update_client_rejects_duplicate_phone(api_authed_client):
    first = api_authed_client.post(
        "/api/clients",
        json={"name": "Pizzaria Um", "phone": "11900001111"},
    ).json()
    second = api_authed_client.post(
        "/api/clients",
        json={"name": "Pizzaria Dois", "phone": "11900002222"},
    ).json()

    r = api_authed_client.patch(
        f"/api/clients/{second['id']}",
        json={"phone": first["phone"]},
    )

    assert r.status_code == 409


def test_delete_client_without_orders(api_authed_client):
    created = api_authed_client.post(
        "/api/clients",
        json={"name": "Pizzaria Excluir", "phone": "11933334444"},
    ).json()

    r = api_authed_client.delete(f"/api/clients/{created['id']}")

    assert r.status_code == 204
    assert api_authed_client.get(f"/api/clients/{created['id']}").status_code == 404


def test_delete_client_with_orders_is_blocked(api_authed_client, db, sample_template):
    created = api_authed_client.post(
        "/api/clients",
        json={"name": "Pizzaria Com Pedido", "phone": "11955556666"},
    ).json()
    api_authed_client.post(
        "/api/orders",
        json={"client_id": created["id"], "template_id": sample_template["id"]},
    )

    r = api_authed_client.delete(f"/api/clients/{created['id']}")

    assert r.status_code == 409
