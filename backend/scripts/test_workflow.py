"""End-to-end test of the pre-sales workflow via HTTP API."""

import sys
import json
import requests

BASE = "http://127.0.0.1:8000/api"
PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [OK] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} — {detail}")


def main():
    global PASS, FAIL
    print("=" * 60)
    print("  TESTE DE WORKFLOW COMPLETO")
    print("=" * 60)

    # 1. Catalog
    print("\n--- 1. Catalogo ---")
    r = requests.get(f"{BASE}/catalog")
    check("GET /catalog status", r.status_code == 200)
    catalog = r.json()
    check("Catalogo tem templates", len(catalog) > 0, f"got {len(catalog)}")
    template_id = catalog[0]["id"]
    check("Template tem campos editaveis", len(catalog[0]["editable_fields"]) > 0)

    # 2. Catalog detail
    print("\n--- 2. Detalhe do template ---")
    r = requests.get(f"{BASE}/catalog/{template_id}")
    check("GET /catalog/id status", r.status_code == 200)
    detail = r.json()
    check("Tem filename", bool(detail.get("filename")))
    check("Tem layers", len(detail.get("layers", [])) > 0)

    # 3. Thumbnail
    print("\n--- 3. Thumbnail ---")
    r = requests.get(f"{BASE}/catalog/{template_id}/thumbnail")
    check("GET thumbnail status", r.status_code == 200)
    check("Thumbnail e JPEG", r.headers.get("content-type", "").startswith("image/jpeg"))

    # 4. Create client
    print("\n--- 4. Criar cliente ---")
    r = requests.post(f"{BASE}/clients", json={
        "name": "Pizzaria Vittoria",
        "phone": "(11) 98888-7777",
        "instagram": "@vittoria",
    })
    check("POST /clients status", r.status_code == 200)
    client = r.json()
    client_id = client["id"]
    check("Cliente tem id", client_id > 0)

    # 5. Lookup client
    print("\n--- 5. Buscar cliente ---")
    r = requests.get(f"{BASE}/clients/(11) 98888-7777")
    check("GET /clients/phone status", r.status_code == 200)
    check("Nome correto", r.json()["name"] == "Pizzaria Vittoria")

    # 6. Create order
    print("\n--- 6. Criar pedido ---")
    r = requests.post(f"{BASE}/orders", json={
        "client_id": client_id,
        "template_id": template_id,
        "edit_data": {
            "telefone": "(11) 98888-7777",
            "instagram": "@vittoria",
        },
    })
    check("POST /orders status", r.status_code == 200)
    order = r.json()
    order_id = order["id"]
    check("Status = draft", order["status"] == "draft")
    check("Tem edit_data", "telefone" in order["edit_data"])

    # 7. Generate preview
    print("\n--- 7. Gerar preview ---")
    r = requests.post(f"{BASE}/orders/{order_id}/preview")
    check("POST preview status", r.status_code == 200)
    order = r.json()
    check("Status = preview_sent", order["status"] == "preview_sent")
    check("Tem preview_url", order.get("preview_url") is not None)
    check("Tem changes_applied", len(order.get("changes_applied", [])) > 0)

    # 8. Download preview
    print("\n--- 8. Download preview ---")
    r = requests.get(f"{BASE}/orders/{order_id}/preview")
    check("GET preview status", r.status_code == 200)
    check("Preview e JPEG", r.headers.get("content-type", "").startswith("image/jpeg"))

    # 9. Reject (ask for changes)
    print("\n--- 9. Rejeitar pedido ---")
    r = requests.post(f"{BASE}/orders/{order_id}/reject", json={
        "feedback": "Quero fundo premium e frase 'A Melhor da Regiao!'"
    })
    check("POST reject status", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    order = r.json()
    check("Status = revision", order["status"] == "revision")

    # 10. Update order
    print("\n--- 10. Atualizar pedido ---")
    r = requests.patch(f"{BASE}/orders/{order_id}", json={
        "edit_data": {
            "tema_fundo": "premium",
            "frase": "A Melhor da Regiao!",
            "adicionar_forno_lenha": True,
        }
    })
    check("PATCH order status", r.status_code == 200)
    order = r.json()
    check("Dados merged (telefone preservado)", "telefone" in order["edit_data"])
    check("Tema atualizado", order["edit_data"].get("tema_fundo") == "premium")
    check("Frase adicionada", order["edit_data"].get("frase") == "A Melhor da Regiao!")

    # 11. Regenerate preview
    print("\n--- 11. Regenerar preview ---")
    r = requests.post(f"{BASE}/orders/{order_id}/preview")
    check("POST preview (2) status", r.status_code == 200)
    order = r.json()
    check("Status = preview_sent", order["status"] == "preview_sent")
    check("Tem 2+ revisoes", len(order.get("revisions", [])) >= 2)

    # 12. Approve
    print("\n--- 12. Aprovar pedido ---")
    r = requests.post(f"{BASE}/orders/{order_id}/approve")
    check("POST approve status", r.status_code == 200)
    order = r.json()
    check("Status = production", order["status"] == "production")
    check("Tem cmyk_url", order.get("cmyk_url") is not None)

    # 13. Download production CMYK
    print("\n--- 13. Download CMYK ---")
    r = requests.get(f"{BASE}/orders/{order_id}/production")
    check("GET production status", r.status_code == 200)
    check("CMYK tem conteudo", len(r.content) > 1000)

    # 14. List orders
    print("\n--- 14. Listar pedidos ---")
    r = requests.get(f"{BASE}/orders?status=production")
    check("GET orders status", r.status_code == 200)
    orders = r.json()
    check("Lista contem pedido", any(o["id"] == order_id for o in orders))

    # 15. Order detail with revisions
    print("\n--- 15. Detalhe com revisoes ---")
    r = requests.get(f"{BASE}/orders/{order_id}")
    check("GET order detail status", r.status_code == 200)
    order = r.json()
    check("Tem revisoes", len(order.get("revisions", [])) >= 2)

    # 16. Backward compat: old /api/process
    print("\n--- 16. Backward compat (/api/process) ---")
    r = requests.post(f"{BASE}/process", json={
        "template": "caixa_35cm_teste.psd",
        "command": {"telefone": "(11) 99999-0000"},
    })
    check("POST /process status", r.status_code == 200)
    check("Retorna job_id", bool(r.json().get("job_id")))

    # Summary
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"  Resultado: {PASS}/{total} passed, {FAIL} failed")
    print("=" * 60)

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()
