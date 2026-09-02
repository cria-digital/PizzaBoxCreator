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

CREATE TABLE IF NOT EXISTS crm_profiles (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id             INTEGER NOT NULL UNIQUE REFERENCES clients(id),
    classification        TEXT NOT NULL DEFAULT 'new'
                          CHECK(classification IN ('new','active','vip','at_risk','abandoned','inactive')),
    lifecycle_stage       TEXT NOT NULL DEFAULT 'lead'
                          CHECK(lifecycle_stage IN ('lead','qualified','order_created','preview_sent','revision','approved','production','delivered')),
    score                 INTEGER,
    last_contact_at       TEXT,
    last_order_at         TEXT,
    last_classified_at    TEXT,
    next_reengagement_at  TEXT,
    reengagement_paused   INTEGER NOT NULL DEFAULT 0,
    classification_reason TEXT,
    classification_data   TEXT NOT NULL DEFAULT '{}',
    rule_version          TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_crm_profiles_classification ON crm_profiles(classification);
CREATE INDEX IF NOT EXISTS idx_crm_profiles_lifecycle_stage ON crm_profiles(lifecycle_stage);
CREATE INDEX IF NOT EXISTS idx_crm_profiles_next_reengagement ON crm_profiles(next_reengagement_at);

CREATE TABLE IF NOT EXISTS crm_interactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id        INTEGER NOT NULL REFERENCES clients(id),
    order_id         INTEGER REFERENCES orders(id),
    channel          TEXT NOT NULL CHECK(channel IN ('whatsapp','web','api','system')),
    direction        TEXT NOT NULL CHECK(direction IN ('inbound','outbound','internal')),
    event_type       TEXT NOT NULL,
    payload          TEXT NOT NULL DEFAULT '{}',
    occurred_at      TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    idempotency_key  TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_crm_interactions_client ON crm_interactions(client_id);
CREATE INDEX IF NOT EXISTS idx_crm_interactions_order ON crm_interactions(order_id);
CREATE INDEX IF NOT EXISTS idx_crm_interactions_event_type ON crm_interactions(event_type);
CREATE INDEX IF NOT EXISTS idx_crm_interactions_occurred_at ON crm_interactions(occurred_at);

CREATE TABLE IF NOT EXISTS crm_classification_events (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id                INTEGER NOT NULL REFERENCES clients(id),
    previous_classification  TEXT CHECK(previous_classification IN ('new','active','vip','at_risk','abandoned','inactive')),
    new_classification       TEXT NOT NULL CHECK(new_classification IN ('new','active','vip','at_risk','abandoned','inactive')),
    reason                   TEXT NOT NULL,
    evidence                 TEXT NOT NULL DEFAULT '{}',
    rule_version             TEXT NOT NULL,
    created_at               TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_crm_classification_events_client ON crm_classification_events(client_id);
CREATE INDEX IF NOT EXISTS idx_crm_classification_events_created ON crm_classification_events(created_at);

CREATE TABLE IF NOT EXISTS crm_reengagement_tasks (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id      INTEGER NOT NULL REFERENCES clients(id),
    order_id       INTEGER REFERENCES orders(id),
    reason         TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK(status IN ('pending','sent','skipped','failed')),
    scheduled_for  TEXT NOT NULL,
    attempt_count  INTEGER NOT NULL DEFAULT 0,
    sent_at        TEXT,
    last_error     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_crm_reengagement_client ON crm_reengagement_tasks(client_id);
CREATE INDEX IF NOT EXISTS idx_crm_reengagement_status ON crm_reengagement_tasks(status);
CREATE INDEX IF NOT EXISTS idx_crm_reengagement_scheduled ON crm_reengagement_tasks(scheduled_for);

CREATE TABLE IF NOT EXISTS order_status_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders(id),
    from_status  TEXT CHECK(from_status IN ('draft','preview_sent','revision','approved','production','delivered')),
    to_status    TEXT NOT NULL CHECK(to_status IN ('draft','preview_sent','revision','approved','production','delivered')),
    source       TEXT NOT NULL DEFAULT 'system',
    actor        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_order_status_events_order ON order_status_events(order_id);
CREATE INDEX IF NOT EXISTS idx_order_status_events_status ON order_status_events(to_status);
CREATE INDEX IF NOT EXISTS idx_order_status_events_created ON order_status_events(created_at);
