"""SQLAlchemy ORM models for all database tables."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrderStatus(str, enum.Enum):
    draft = "draft"
    preview_sent = "preview_sent"
    revision = "revision"
    approved = "approved"
    production = "production"
    delivered = "delivered"


class CrmClassification(str, enum.Enum):
    new = "new"
    active = "active"
    vip = "vip"
    at_risk = "at_risk"
    abandoned = "abandoned"
    inactive = "inactive"


class CrmLifecycleStage(str, enum.Enum):
    lead = "lead"
    qualified = "qualified"
    order_created = "order_created"
    preview_sent = "preview_sent"
    revision = "revision"
    approved = "approved"
    production = "production"
    delivered = "delivered"


class CrmChannel(str, enum.Enum):
    whatsapp = "whatsapp"
    web = "web"
    api = "api"
    system = "system"


class CrmDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"
    internal = "internal"


class ReengagementStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    skipped = "skipped"
    failed = "failed"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    instagram: Mapped[str | None] = mapped_column(String, nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    orders: Mapped[list["Order"]] = relationship("Order", back_populates="client")
    crm_profile: Mapped["CrmProfile"] = relationship(
        "CrmProfile", back_populates="client", uselist=False
    )


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    size_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_type: Mapped[str] = mapped_column(String, nullable=False, default="pizza")
    editable_fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    calibration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    thumbnail: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    orders: Mapped[list["Order"]] = relationship("Order", back_populates="template")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("templates.id"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", create_constraint=True),
        nullable=False,
        default=OrderStatus.draft,
    )
    quantidade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edit_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_psd: Mapped[str | None] = mapped_column(String, nullable=True)
    preview_jpg: Mapped[str | None] = mapped_column(String, nullable=True)
    cmyk_psd: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    client: Mapped["Client"] = relationship("Client", back_populates="orders")
    template: Mapped["Template"] = relationship("Template", back_populates="orders")
    revisions: Mapped[list["OrderRevision"]] = relationship(
        "OrderRevision", back_populates="order", order_by="OrderRevision.revision_number"
    )

    __table_args__ = (
        Index("idx_orders_client", "client_id"),
        Index("idx_orders_status", "status"),
    )


class OrderRevision(Base):
    __tablename__ = "order_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    edit_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    preview_jpg: Mapped[str | None] = mapped_column(String, nullable=True)
    preview_source: Mapped[str] = mapped_column(String, nullable=False, default="psd")
    feedback: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped["Order"] = relationship("Order", back_populates="revisions")

    __table_args__ = (
        UniqueConstraint("order_id", "revision_number", name="uq_order_revision"),
        Index("idx_revisions_order", "order_id"),
    )


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    wamid: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("orders.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_wa_messages_order", "order_id"),)


class AdminAccount(Base):
    __tablename__ = "admin_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WhatsAppConfig(Base):
    __tablename__ = "whatsapp_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str | None] = mapped_column(String, nullable=True)
    phone_number_id: Mapped[str | None] = mapped_column(String, nullable=True)
    verify_token: Mapped[str | None] = mapped_column(String, nullable=True)
    app_secret: Mapped[str | None] = mapped_column(String, nullable=True)
    api_version: Mapped[str] = mapped_column(String, nullable=False, default="v21.0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (CheckConstraint("id = 1", name="wa_config_single_row"),)


class AuditLog(Base):
    """Immutable audit trail: who did what, when, to which order."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("orders.id"), nullable=True
    )
    username: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_audit_log_order", "order_id"),
        Index("idx_audit_log_user", "username"),
    )


class CrmProfile(Base):
    __tablename__ = "crm_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id"), unique=True, nullable=False
    )
    classification: Mapped[CrmClassification] = mapped_column(
        Enum(CrmClassification, name="crm_classification", create_constraint=True),
        nullable=False,
        default=CrmClassification.new,
    )
    lifecycle_stage: Mapped[CrmLifecycleStage] = mapped_column(
        Enum(CrmLifecycleStage, name="crm_lifecycle_stage", create_constraint=True),
        nullable=False,
        default=CrmLifecycleStage.lead,
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_reengagement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reengagement_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    classification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rule_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    client: Mapped["Client"] = relationship("Client", back_populates="crm_profile")

    __table_args__ = (
        Index("idx_crm_profiles_classification", "classification"),
        Index("idx_crm_profiles_lifecycle_stage", "lifecycle_stage"),
        Index("idx_crm_profiles_next_reengagement", "next_reengagement_at"),
    )


class CrmInteraction(Base):
    __tablename__ = "crm_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    channel: Mapped[CrmChannel] = mapped_column(
        Enum(CrmChannel, name="crm_channel", create_constraint=True), nullable=False
    )
    direction: Mapped[CrmDirection] = mapped_column(
        Enum(CrmDirection, name="crm_direction", create_constraint=True), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    __table_args__ = (
        Index("idx_crm_interactions_client", "client_id"),
        Index("idx_crm_interactions_order", "order_id"),
        Index("idx_crm_interactions_event_type", "event_type"),
        Index("idx_crm_interactions_occurred_at", "occurred_at"),
    )


class CrmClassificationEvent(Base):
    __tablename__ = "crm_classification_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False)
    previous_classification: Mapped[CrmClassification | None] = mapped_column(
        Enum(CrmClassification, name="crm_classification", create_constraint=True),
        nullable=True,
    )
    new_classification: Mapped[CrmClassification] = mapped_column(
        Enum(CrmClassification, name="crm_classification", create_constraint=True),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rule_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_crm_classification_events_client", "client_id"),
        Index("idx_crm_classification_events_created", "created_at"),
    )


class CrmReengagementTask(Base):
    __tablename__ = "crm_reengagement_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ReengagementStatus] = mapped_column(
        Enum(ReengagementStatus, name="reengagement_status", create_constraint=True),
        nullable=False,
        default=ReengagementStatus.pending,
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_crm_reengagement_client", "client_id"),
        Index("idx_crm_reengagement_status", "status"),
        Index("idx_crm_reengagement_scheduled", "scheduled_for"),
    )


class OrderStatusEvent(Base):
    __tablename__ = "order_status_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    from_status: Mapped[OrderStatus | None] = mapped_column(
        Enum(OrderStatus, name="order_status", create_constraint=True),
        nullable=True,
    )
    to_status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", create_constraint=True),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String, nullable=False, default="system")
    actor: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_order_status_events_order", "order_id"),
        Index("idx_order_status_events_status", "to_status"),
        Index("idx_order_status_events_created", "created_at"),
    )
