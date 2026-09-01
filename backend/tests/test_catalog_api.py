def test_catalog_requires_login(api_client):
    r = api_client.get("/api/catalog")
    assert r.status_code == 401


def test_list_catalog_returns_active_templates(api_authed_client, sample_template):
    r = api_authed_client.get("/api/catalog")
    assert r.status_code == 200
    items = r.json()
    assert any(t["id"] == sample_template["id"] for t in items)


def test_list_catalog_excludes_inactive_templates(api_authed_client, db, sample_template):
    from sqlalchemy import update
    from app.db.models import Template
    stmt = update(Template).where(Template.id == sample_template["id"]).values(active=False)
    db.execute(stmt)
    db.commit()

    r = api_authed_client.get("/api/catalog")
    assert r.status_code == 200
    assert all(t["id"] != sample_template["id"] for t in r.json())


def test_catalog_detail_returns_template_even_without_psd_on_disk(api_authed_client, sample_template):
    # sample_template's filename ("dummy.psd") doesn't actually exist on disk --
    # the endpoint must degrade to an empty layer list, not 500.
    r = api_authed_client.get(f"/api/catalog/{sample_template['id']}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["filename"] == "dummy.psd"
    assert detail["layers"] == []


def test_catalog_detail_404_for_missing_template(api_authed_client, sample_template):
    r = api_authed_client.get("/api/catalog/999999")
    assert r.status_code == 404


def test_catalog_thumbnail_404_when_not_set(api_authed_client, sample_template):
    r = api_authed_client.get(f"/api/catalog/{sample_template['id']}/thumbnail")
    assert r.status_code == 404
