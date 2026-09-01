from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field, field_validator

from app.utils.phone import normalize_phone


class TemaFundo(str, Enum):
    tradicional = "tradicional"
    premium = "premium"


class EditCommand(BaseModel):
    """Structured command extracted by the LLM from natural language."""
    telefone: str | None = Field(None, description="Phone number to set")
    instagram: str | None = Field(None, description="Instagram handle")
    frase: str | None = Field(None, description="Custom phrase (e.g. 'Bom Apetite!')")
    tema_fundo: TemaFundo | None = Field(None, description="Background theme")
    adicionar_selo_entrega: bool = False
    adicionar_forno_lenha: bool = False
    logo_path: str | None = Field(None, description="Path to logo image file")


class ProcessRequest(BaseModel):
    """Input from the API: natural language or structured command."""
    template: str = Field(description="Template PSD filename in gabaritos/")
    message: str | None = Field(None, description="Natural language instruction")
    command: EditCommand | None = Field(None, description="Structured command (skips LLM)")


class LayerInfo(BaseModel):
    name: str
    layer_type: str
    visible: bool
    editable: bool = False
    current_text: str | None = None


class TemplateInfo(BaseModel):
    filename: str
    width: int
    height: int
    layers: list[LayerInfo]


class JobResult(BaseModel):
    job_id: str
    template: str
    command: EditCommand
    output_psd: str
    preview_jpg: str
    changes_applied: list[str]


# ---------------------------------------------------------------------------
# Pre-sales workflow models
# ---------------------------------------------------------------------------

class OrderStatus(str, Enum):
    draft = "draft"
    preview_sent = "preview_sent"
    revision = "revision"
    approved = "approved"
    production = "production"
    delivered = "delivered"


class ClientCreate(BaseModel):
    name: str
    phone: str
    instagram: str | None = None
    logo_path: str | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Nome do cliente deve ter pelo menos 2 caracteres")
        return value

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str) -> str:
        normalized = normalize_phone(value)
        if len(normalized) < 10 or len(normalized) > 14:
            raise ValueError("Telefone deve ter entre 10 e 14 digitos")
        return normalized

    @field_validator("instagram")
    @classmethod
    def _normalize_instagram(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        return value if value.startswith("@") else f"@{value}"


class ClientUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    instagram: str | None = None
    logo_path: str | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Nome do cliente deve ter pelo menos 2 caracteres")
        return value

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_phone(value)
        if len(normalized) < 10 or len(normalized) > 14:
            raise ValueError("Telefone deve ter entre 10 e 14 digitos")
        return normalized

    @field_validator("instagram")
    @classmethod
    def _normalize_instagram(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        return value if value.startswith("@") else f"@{value}"


class ClientResponse(BaseModel):
    id: int
    name: str
    phone: str
    instagram: str | None = None
    logo_path: str | None = None
    created_at: str
    updated_at: str


class EditableFieldInfo(BaseModel):
    name: str
    type: str  # text, image, choice, toggle
    label: str
    required: bool = False
    options: list[str] | None = None


class CatalogItem(BaseModel):
    id: int
    display_name: str
    description: str | None = None
    size_cm: int | None = None
    product_type: str
    thumbnail_url: str | None = None
    editable_fields: list[EditableFieldInfo] = []


class CatalogDetail(CatalogItem):
    filename: str
    layers: list[LayerInfo] = []


class OrderCreate(BaseModel):
    client_id: int | None = None
    client_phone: str | None = None
    template_id: int
    quantidade: int | None = Field(None, description="Quantidade de caixas do pedido")
    edit_data: dict = Field(default_factory=dict)
    message: str | None = Field(None, description="Natural language (parsed by AI)")


class OrderUpdate(BaseModel):
    quantidade: int | None = None
    edit_data: dict | None = None
    message: str | None = None


class RevisionResponse(BaseModel):
    id: int
    revision_number: int
    edit_data: dict
    preview_url: str | None = None
    feedback: str | None = None
    created_at: str


class OrderResponse(BaseModel):
    id: int
    client: ClientResponse
    template: CatalogItem
    status: OrderStatus
    quantidade: int | None = None
    edit_data: dict
    preview_url: str | None = None
    cmyk_url: str | None = None
    package_url: str | None = None
    created_at: str
    updated_at: str
    revisions: list[RevisionResponse] = []
    changes_applied: list[str] = []
