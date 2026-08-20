"""Smoke test for the Meta WhatsApp Cloud API credentials in .env.

Sends one free-form text message to a phone number, using the same
WhatsAppClient the app uses in production. Run this after filling in
META_WHATSAPP_TOKEN/META_PHONE_NUMBER_ID to confirm they actually work,
before wiring up the webhook.

Usage:
    python scripts/whatsapp_send_test.py 5511999998888
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.integrations.whatsapp_client import WhatsAppClient, WhatsAppOutsideWindowError
from app.utils.phone import normalize_phone


def main():
    if len(sys.argv) != 2:
        print("Uso: python scripts/whatsapp_send_test.py <telefone com DDI, ex: 5511999998888>")
        sys.exit(1)

    if not settings.whatsapp_enabled:
        print("WhatsApp nao configurado: defina META_WHATSAPP_TOKEN e META_PHONE_NUMBER_ID no .env")
        sys.exit(1)

    phone = normalize_phone(sys.argv[1])
    print(f"Enviando mensagem de teste para {phone} via phone_number_id={settings.meta_phone_number_id}...")

    client = WhatsAppClient()
    try:
        result = client.send_text(phone, "Teste de integracao Pizza Box Agent - tudo funcionando!")
        print("OK:", result)
    except WhatsAppOutsideWindowError:
        print(
            "Credenciais validas, mas esse numero esta fora da janela de 24h "
            "(precisa ter mandado mensagem pra voce recentemente, ou usar um template aprovado)."
        )
    except Exception as e:
        print(f"Falhou: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
