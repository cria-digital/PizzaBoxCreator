import logging
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    # Qual IA usar: "auto" (usa a chave que estiver configurada), "anthropic" ou "gemini".
    ai_provider: str = "auto"
    # Geracao de imagem (preview de aprovacao do cliente). So o Gemini gera imagem aqui.
    gemini_image_model: str = "gemini-3-pro-image"
    ai_preview_aspect_ratio: str = "16:9"
    # Imagem de referencia (opcional) usada como guia de layout de caixa planificada. Vazio = so texto.
    ai_preview_reference: str = ""
    templates_dir: Path = Path("gabaritos")
    output_dir: Path = Path("storage/output")
    preview_dir: Path = Path("storage/preview")
    temp_dir: Path = Path("temp")
    database_url: str = "sqlite:///storage/pizzabox.db"
    db_path: Path = Path("storage/pizzabox.db")
    thumbnails_dir: Path = Path("storage/thumbnails")
    logos_dir: Path = Path("storage/logos")
    admin_user: str = "admin"
    admin_password: str
    secret_key: str
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    # Comma-separated allowed CORS origins. Default "*" is fine for local dev; set explicit
    # origins before exposing the app (e.g. "https://admin.suaempresa.com").
    cors_origins: str = "*"
    preview_max_width: int = 1200
    preview_quality: int = 85
    # Resolucao (DPI) gravada no PSD CMYK de producao. Os gabaritos costumam vir marcados
    # como 72 DPI; a gráfica precisa de 300. Ajuste por aqui se o tamanho fisico exigir outro.
    production_dpi: int = 300
    logo_remove_background: bool = True
    secure_cookies: bool = False
    # AI cost guard — limits and caching for AI image generation previews.
    ai_preview_max_per_order: int = 5
    ai_preview_rate_window_hours: int = 24
    ai_preview_cache_enabled: bool = True
    ai_preview_cache_ttl_hours: int = 24
    # WAL gives concurrent reads in production; the test suite overrides this to a single-file
    # rollback journal to avoid the WAL -wal/-shm multi-connection corruption seen on Windows.
    sqlite_journal_mode: str = "WAL"
    sqlite_busy_timeout: int = 5000  # ms
    login_max_attempts: int = 5
    login_lockout_seconds: int = 300

    meta_whatsapp_token: str = ""
    meta_phone_number_id: str = ""
    meta_webhook_verify_token: str = ""
    meta_app_secret: str = ""
    meta_api_version: str = "v21.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.meta_whatsapp_token and self.meta_phone_number_id)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]

    @model_validator(mode="after")
    def _warn_weak_credentials(self) -> "Settings":
        """Flag weak ADMIN_PASSWORD/SECRET_KEY instead of failing startup.

        Kept as a warning (not a hard error) because short passwords are
        legitimately used for local/dev testing; this just makes sure it's
        not silently carried into a real deployment.
        """
        if len(self.admin_password) < 12:
            logger.warning(
                "ADMIN_PASSWORD tem menos de 12 caracteres -- ok para testes locais, "
                "troque por algo mais forte antes de expor o app fora da sua maquina."
            )
        if len(self.secret_key) < 16:
            logger.warning(
                "SECRET_KEY tem menos de 16 caracteres -- assina os cookies de sessao, "
                "use algo mais longo/aleatorio antes de expor o app fora da sua maquina."
            )
        return self

    def ensure_dirs(self):
        for d in [self.templates_dir, self.output_dir, self.preview_dir, self.temp_dir,
                  self.thumbnails_dir, self.logos_dir]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
