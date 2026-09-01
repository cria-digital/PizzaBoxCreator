"""Data access layer — all database operations via SQLAlchemy ORM."""

from __future__ import annotations

from sqlalchemy import func, select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    AdminAccount,
    Client,
    Order,
    OrderRevision,
    Template,
    WhatsAppConfig,
    WhatsAppMessage,
)
from app.utils.phone import normalize_phone


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

def client_create(db: Session, name: str, phone: str,
                  instagram: str | None = None, logo_path: str | None = None) -> dict:
    client = Client(
        name=name,
        phone=normalize_phone(phone),
        instagram=instagram,
        logo_path=logo_path,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return _client_to_dict(client)


def client_upsert(db: Session, name: str, phone: str,
                  instagram: str | None = None, logo_path: str | None = None) -> dict:
    existing = client_get_by_phone(db, phone)
    if existing:
        fields = {}
        if name:
            fields["name"] = name
        if instagram is not None:
            fields["instagram"] = instagram
        if logo_path is not None:
            fields["logo_path"] = logo_path
        if fields:
            return client_update(db, existing["id"], **fields)
        return existing
    return client_create(db, name, phone, instagram, logo_path)


def client_get(db: Session, client_id: int) -> dict | None:
    client = db.get(Client, client_id)
    return _client_to_dict(client) if client else None


def client_get_by_phone(db: Session, phone: str) -> dict | None:
    stmt = select(Client).where(Client.phone == normalize_phone(phone))
    client = db.scalar(stmt)
    return _client_to_dict(client) if client else None


def client_update(db: Session, client_id: int, **fields) -> dict:
    if "phone" in fields and fields["phone"] is not None:
        fields["phone"] = normalize_phone(fields["phone"])
    stmt = (
        update(Client)
        .where(Client.id == client_id)
        .values(**fields)
    )
    try:
        db.execute(stmt)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    return client_get(db, client_id)


def client_order_count(db: Session, client_id: int) -> int:
    stmt = select(func.count()).select_from(Order).where(Order.client_id == client_id)
    return db.scalar(stmt)


def client_delete(db: Session, client_id: int) -> None:
    stmt = delete(Client).where(Client.id == client_id)
    db.execute(stmt)
    db.commit()


def client_list(db: Session, search: str | None = None) -> list[dict]:
    stmt = select(Client).order_by(Client.name)
    if search:
        stmt = stmt.where(
            Client.name.ilike(f"%{search}%") | Client.phone.ilike(f"%{search}%")
        )
    return [_client_to_dict(c) for c in db.scalars(stmt)]


def _client_to_dict(client: Client) -> dict:
    return {
        "id": client.id,
        "name": client.name,
        "phone": client.phone,
        "instagram": client.instagram,
        "logo_path": client.logo_path,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

def template_create(db: Session, filename: str, display_name: str,
                    description: str | None = None, size_cm: int | None = None,
                    product_type: str = "pizza", editable_fields: list | None = None,
                    thumbnail: str | None = None) -> dict:
    existing = template_get_by_filename(db, filename)
    if existing:
        return existing
    tmpl = Template(
        filename=filename,
        display_name=display_name,
        description=description,
        size_cm=size_cm,
        product_type=product_type,
        editable_fields=editable_fields or [],
        thumbnail=thumbnail,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return _template_to_dict(tmpl)


def template_get(db: Session, template_id: int) -> dict | None:
    tmpl = db.get(Template, template_id)
    return _template_to_dict(tmpl) if tmpl else None


def template_get_by_filename(db: Session, filename: str) -> dict | None:
    stmt = select(Template).where(Template.filename == filename)
    tmpl = db.scalar(stmt)
    return _template_to_dict(tmpl) if tmpl else None


def template_list_active(db: Session) -> list[dict]:
    stmt = (
        select(Template)
        .where(Template.active == True)  # noqa: E712
        .order_by(Template.product_type, Template.size_cm)
    )
    return [_template_to_dict(t) for t in db.scalars(stmt)]


def template_list_all(db: Session) -> list[dict]:
    stmt = select(Template).order_by(Template.active.desc(), Template.product_type, Template.size_cm)
    return [_template_to_dict(t) for t in db.scalars(stmt)]


_TEMPLATE_EDITABLE = ("display_name", "description", "size_cm", "product_type", "thumbnail")


def template_update(db: Session, template_id: int, **fields) -> dict | None:
    fields = {k: v for k, v in fields.items() if k in _TEMPLATE_EDITABLE}
    if fields:
        stmt = update(Template).where(Template.id == template_id).values(**fields)
        db.execute(stmt)
        db.commit()
    return template_get(db, template_id)


def template_set_active(db: Session, template_id: int, active: bool) -> None:
    stmt = update(Template).where(Template.id == template_id).values(active=active)
    db.execute(stmt)
    db.commit()


def template_order_count(db: Session, template_id: int) -> int:
    stmt = select(func.count()).select_from(Order).where(Order.template_id == template_id)
    return db.scalar(stmt)


def template_delete(db: Session, template_id: int) -> None:
    stmt = delete(Template).where(Template.id == template_id)
    db.execute(stmt)
    db.commit()


def template_set_calibration(db: Session, template_id: int, calibration: dict) -> None:
    stmt = update(Template).where(Template.id == template_id).values(calibration=calibration)
    db.execute(stmt)
    db.commit()


def _template_to_dict(tmpl: Template) -> dict:
    return {
        "id": tmpl.id,
        "filename": tmpl.filename,
        "display_name": tmpl.display_name,
        "description": tmpl.description,
        "size_cm": tmpl.size_cm,
        "product_type": tmpl.product_type,
        "editable_fields": tmpl.editable_fields or [],
        "calibration": tmpl.calibration or {},
        "thumbnail": tmpl.thumbnail,
        "active": tmpl.active,
        "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
    }


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

def order_create(db: Session, client_id: int, template_id: int,
                 edit_data: dict | None = None, quantidade: int | None = None,
                 created_by: str | None = None) -> dict:
    order = Order(
        client_id=client_id,
        template_id=template_id,
        edit_data=edit_data or {},
        quantidade=quantidade,
        created_by=created_by,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return _order_to_dict(order)


def order_get(db: Session, order_id: int) -> dict | None:
    order = db.get(Order, order_id)
    return _order_to_dict(order) if order else None


def order_update_edit_data(db: Session, order_id: int, edit_data: dict) -> dict:
    order = db.get(Order, order_id)
    merged = {**(order.edit_data or {}), **edit_data}
    stmt = update(Order).where(Order.id == order_id).values(edit_data=merged)
    db.execute(stmt)
    db.commit()
    return order_get(db, order_id)


def order_update_quantidade(db: Session, order_id: int, quantidade: int) -> dict:
    stmt = update(Order).where(Order.id == order_id).values(quantidade=quantidade)
    db.execute(stmt)
    db.commit()
    return order_get(db, order_id)


def order_update_status(db: Session, order_id: int, status: str) -> dict:
    stmt = update(Order).where(Order.id == order_id).values(status=status)
    db.execute(stmt)
    db.commit()
    return order_get(db, order_id)


def order_set_paths(db: Session, order_id: int,
                    output_psd: str | None = None, preview_jpg: str | None = None,
                    cmyk_psd: str | None = None) -> dict:
    values = {}
    if output_psd is not None:
        values["output_psd"] = output_psd
    if preview_jpg is not None:
        values["preview_jpg"] = preview_jpg
    if cmyk_psd is not None:
        values["cmyk_psd"] = cmyk_psd
    if values:
        stmt = update(Order).where(Order.id == order_id).values(**values)
        db.execute(stmt)
        db.commit()
    return order_get(db, order_id)


def order_list(db: Session, status: str | None = None,
               client_id: int | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    stmt = select(Order).order_by(Order.updated_at.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    if client_id:
        stmt = stmt.where(Order.client_id == client_id)
    stmt = stmt.limit(limit).offset(offset)
    return [_order_to_dict(o) for o in db.scalars(stmt)]


def order_get_active_for_client(db: Session, client_id: int) -> dict | None:
    from app.db.models import OrderStatus
    stmt = (
        select(Order)
        .where(Order.client_id == client_id)
        .where(Order.status.notin_([OrderStatus.production, OrderStatus.delivered]))
        .order_by(Order.updated_at.desc())
        .limit(1)
    )
    order = db.scalar(stmt)
    return _order_to_dict(order) if order else None


def _order_to_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "client_id": order.client_id,
        "template_id": order.template_id,
        "status": order.status.value if order.status else None,
        "quantidade": order.quantidade,
        "edit_data": order.edit_data or {},
        "output_psd": order.output_psd,
        "preview_jpg": order.preview_jpg,
        "cmyk_psd": order.cmyk_psd,
        "created_by": order.created_by,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Order Revisions
# ---------------------------------------------------------------------------

def revision_create(db: Session, order_id: int, revision_number: int,
                    edit_data: dict, preview_jpg: str | None = None,
                    feedback: str | None = None,
                    preview_source: str = "psd") -> dict:
    rev = OrderRevision(
        order_id=order_id,
        revision_number=revision_number,
        edit_data=edit_data,
        preview_jpg=preview_jpg,
        preview_source=preview_source,
        feedback=feedback,
    )
    db.add(rev)
    db.commit()
    db.refresh(rev)
    return revision_get_latest(db, order_id)


def revision_list(db: Session, order_id: int) -> list[dict]:
    stmt = (
        select(OrderRevision)
        .where(OrderRevision.order_id == order_id)
        .order_by(OrderRevision.revision_number)
    )
    return [_revision_to_dict(r) for r in db.scalars(stmt)]


def revision_get_latest(db: Session, order_id: int) -> dict | None:
    stmt = (
        select(OrderRevision)
        .where(OrderRevision.order_id == order_id)
        .order_by(OrderRevision.revision_number.desc())
        .limit(1)
    )
    rev = db.scalar(stmt)
    return _revision_to_dict(rev) if rev else None


def revision_count(db: Session, order_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(OrderRevision)
        .where(OrderRevision.order_id == order_id)
    )
    return db.scalar(stmt)


def _revision_to_dict(rev: OrderRevision) -> dict:
    return {
        "id": rev.id,
        "order_id": rev.order_id,
        "revision_number": rev.revision_number,
        "edit_data": rev.edit_data or {},
        "preview_jpg": rev.preview_jpg,
        "preview_source": rev.preview_source,
        "feedback": rev.feedback,
        "created_at": rev.created_at.isoformat() if rev.created_at else None,
    }


# ---------------------------------------------------------------------------
# WhatsApp messages (idempotency log for the webhook)
# ---------------------------------------------------------------------------

def wa_message_claim(db: Session, wamid: str) -> bool:
    existing = db.get(WhatsAppMessage, wamid)
    if existing:
        return False
    msg = WhatsAppMessage(wamid=wamid)
    db.add(msg)
    db.commit()
    return True


def wa_message_set_order(db: Session, wamid: str, order_id: int) -> None:
    stmt = update(WhatsAppMessage).where(WhatsAppMessage.wamid == wamid).values(order_id=order_id)
    db.execute(stmt)
    db.commit()


# ---------------------------------------------------------------------------
# Admin Account
# ---------------------------------------------------------------------------

def admin_account_get(db: Session, username: str | None = None) -> dict | None:
    if username is not None:
        stmt = select(AdminAccount).where(AdminAccount.username == username)
        account = db.scalar(stmt)
        return _admin_to_dict(account) if account else None
    stmt = select(AdminAccount).order_by(AdminAccount.id).limit(1)
    account = db.scalar(stmt)
    return _admin_to_dict(account) if account else None


def admin_account_set(db: Session, username: str, password_hash: str,
                      account_id: int | None = None) -> dict:
    account = db.get(AdminAccount, account_id) if account_id is not None else None
    if account is None:
        account = db.scalar(select(AdminAccount).where(AdminAccount.username == username))
    if account:
        account.username = username
        account.password_hash = password_hash
    else:
        account = AdminAccount(username=username, password_hash=password_hash)
        db.add(account)
    db.commit()
    db.refresh(account)
    return _admin_to_dict(account)


def admin_account_any(db: Session) -> bool:
    return bool(db.scalar(select(func.count()).select_from(AdminAccount)))


def _admin_to_dict(account: AdminAccount) -> dict:
    return {
        "id": account.id,
        "username": account.username,
        "password_hash": account.password_hash,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }


# ---------------------------------------------------------------------------
# WhatsApp Config
# ---------------------------------------------------------------------------

def whatsapp_config_get(db: Session) -> dict | None:
    config = db.get(WhatsAppConfig, 1)
    return _wa_config_to_dict(config) if config else None


def whatsapp_config_set(db: Session, *, token: str | None, phone_number_id: str | None,
                         verify_token: str | None, app_secret: str | None, api_version: str) -> dict:
    config = db.get(WhatsAppConfig, 1)
    if config:
        config.token = token
        config.phone_number_id = phone_number_id
        config.verify_token = verify_token
        config.app_secret = app_secret
        config.api_version = api_version
    else:
        config = WhatsAppConfig(
            id=1,
            token=token,
            phone_number_id=phone_number_id,
            verify_token=verify_token,
            app_secret=app_secret,
            api_version=api_version,
        )
        db.add(config)
    db.commit()
    db.refresh(config)
    return _wa_config_to_dict(config)


def _wa_config_to_dict(config: WhatsAppConfig) -> dict:
    return {
        "id": config.id,
        "token": config.token,
        "phone_number_id": config.phone_number_id,
        "verify_token": config.verify_token,
        "app_secret": config.app_secret,
        "api_version": config.api_version,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def audit_log(db: Session, username: str, action: str,
              order_id: int | None = None, details: dict | None = None) -> None:
    """Write an entry to the audit log. Never fails — errors are swallowed to avoid
    blocking the main operation."""
    try:
        from app.db.models import AuditLog
        entry = AuditLog(
            order_id=order_id,
            username=username,
            action=action,
            details=details,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()


def audit_log_list(db: Session, order_id: int | None = None,
                   limit: int = 100) -> list[dict]:
    """Read recent audit log entries, optionally filtered by order."""
    from app.db.models import AuditLog
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if order_id is not None:
        stmt = stmt.where(AuditLog.order_id == order_id)
    return [
        {
            "id": e.id,
            "order_id": e.order_id,
            "username": e.username,
            "action": e.action,
            "details": e.details,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in db.scalars(stmt).all()
    ]
