CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL UNIQUE,
    instagram   TEXT,
    logo_path   TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone);

CREATE TABLE IF NOT EXISTS templates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    description     TEXT,
    size_cm         INTEGER,
    product_type    TEXT NOT NULL DEFAULT 'pizza',
    editable_fields TEXT NOT NULL DEFAULT '[]',
    calibration     TEXT NOT NULL DEFAULT '{}',
    thumbnail       TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id    INTEGER NOT NULL REFERENCES clients(id),
    template_id  INTEGER NOT NULL REFERENCES templates(id),
    status       TEXT NOT NULL DEFAULT 'draft'
                 CHECK(status IN ('draft','preview_sent','revision','approved','production','delivered')),
    quantidade   INTEGER,
    edit_data    TEXT NOT NULL DEFAULT '{}',
    output_psd   TEXT,
    preview_jpg  TEXT,
    cmyk_psd     TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_client ON orders(client_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

CREATE TABLE IF NOT EXISTS order_revisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        INTEGER NOT NULL REFERENCES orders(id),
    revision_number INTEGER NOT NULL,
    edit_data       TEXT NOT NULL DEFAULT '{}',
    preview_jpg     TEXT,
    preview_source  TEXT NOT NULL DEFAULT 'psd',
    feedback        TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(order_id, revision_number)
);

CREATE TABLE IF NOT EXISTS whatsapp_messages (
    wamid       TEXT PRIMARY KEY,
    order_id    INTEGER REFERENCES orders(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Admin users saved via /configuracoes/conta or bootstrap tooling. Until any row exists,
-- login falls back to ADMIN_USER/ADMIN_PASSWORD from .env (first-run bootstrap only).
CREATE TABLE IF NOT EXISTS admin_account (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Single-row table: WhatsApp Cloud API credentials configured via the settings
-- screen (/configuracoes/whatsapp) instead of editing .env by hand.
CREATE TABLE IF NOT EXISTS whatsapp_config (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    token            TEXT,
    phone_number_id  TEXT,
    verify_token     TEXT,
    app_secret       TEXT,
    api_version      TEXT NOT NULL DEFAULT 'v21.0',
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
