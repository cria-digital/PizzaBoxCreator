"""FastAPI routes for the Pizza Box Agent."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.api.auth import require_api_user
from app.db.session import get_db
from app.models.commands import (
    EditCommand,
    JobResult,
    ProcessRequest,
    TemplateInfo,
)
from app.psd.engine import PsdEngine
from app.psd.inspector import inspect_template
from app.psd.renderer import generate_preview

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_api_user)])


@router.get("/templates", response_model=list[str])
def list_templates(db: Session = Depends(get_db)):
    """List available PSD templates."""
    templates = list(settings.templates_dir.glob("*.psd"))
    return [t.name for t in templates]


@router.get("/templates/{filename}/layers", response_model=TemplateInfo)
def get_template_layers(filename: str, db: Session = Depends(get_db)):
    """Inspect layers of a template."""
    path = settings.templates_dir / filename
    if not path.exists():
        raise HTTPException(404, f"Template '{filename}' not found")
    return inspect_template(path)


@router.post("/process", response_model=JobResult)
def process_design(request: ProcessRequest, db: Session = Depends(get_db)):
    """Process a design request: natural language or structured command."""
    template_path = settings.templates_dir / request.template
    if not template_path.exists():
        raise HTTPException(404, f"Template '{request.template}' not found")

    if request.command:
        cmd = request.command
    elif request.message:
        try:
            if settings.anthropic_api_key:
                from app.ai.agent import DesignAgent
                agent = DesignAgent()
                cmd = agent.parse_message(request.message)
            else:
                from app.ai.agent import parse_message_offline
                cmd = parse_message_offline(request.message)
        except Exception as e:
            logger.exception("Failed to parse message")
            raise HTTPException(422, f"Could not interpret message: {e}")
    else:
        raise HTTPException(400, "Provide either 'message' or 'command'")

    return _execute_edit(template_path, cmd)


@router.post("/process-upload", response_model=JobResult)
async def process_with_logo(
    template: str = Form(...),
    message: str = Form(None),
    telefone: str = Form(None),
    instagram: str = Form(None),
    frase: str = Form(None),
    tema_fundo: str = Form(None),
    logo: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    """Process with optional logo upload (multipart form)."""
    template_path = settings.templates_dir / template
    if not template_path.exists():
        raise HTTPException(404, f"Template '{template}' not found")

    logo_path = None
    if logo:
        from app.services.logo_service import prepare_logo
        dest = settings.temp_dir / f"{uuid.uuid4().hex}_{Path(logo.filename).stem}.png"
        logo_path = str(prepare_logo(await logo.read(), dest))

    if message:
        try:
            from app.ai.providers import ai_configured
            if ai_configured():
                from app.ai.agent import DesignAgent
                cmd = DesignAgent().parse_message(message, logo_path=logo_path)
            else:
                from app.ai.agent import parse_message_offline
                cmd = parse_message_offline(message)
                if logo_path:
                    cmd.logo_path = logo_path
        except Exception as e:
            logger.exception("Failed to parse message")
            raise HTTPException(422, f"Could not interpret message: {e}")
    else:
        cmd = EditCommand(
            telefone=telefone,
            instagram=instagram,
            frase=frase,
            tema_fundo=tema_fundo,
            logo_path=logo_path,
        )

    return _execute_edit(template_path, cmd)


@router.get("/preview/{job_id}")
def get_preview(job_id: str, db: Session = Depends(get_db)):
    """Download the preview JPG for a job."""
    path = settings.preview_dir / f"{job_id}.jpg"
    if not path.exists():
        raise HTTPException(404, "Preview not found")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/download/{job_id}")
def download_psd(job_id: str, db: Session = Depends(get_db)):
    """Download the output PSD (RGB) for a job."""
    path = settings.output_dir / f"{job_id}.psd"
    if not path.exists():
        raise HTTPException(404, "Output PSD not found")
    return FileResponse(path, media_type="application/octet-stream", filename=f"{job_id}.psd")


@router.get("/download/{job_id}/cmyk")
def download_psd_cmyk(job_id: str, db: Session = Depends(get_db)):
    """Download the output PSD converted to CMYK for print production."""
    rgb_path = settings.output_dir / f"{job_id}.psd"
    if not rgb_path.exists():
        raise HTTPException(404, "Output PSD not found")

    cmyk_path = settings.output_dir / f"{job_id}_cmyk.psd"
    if not cmyk_path.exists():
        engine = PsdEngine(rgb_path)
        engine.save_as_cmyk(cmyk_path, source_psd=rgb_path)

    return FileResponse(
        cmyk_path,
        media_type="application/octet-stream",
        filename=f"{job_id}_cmyk.psd",
    )


def _execute_edit(template_path: Path, cmd: EditCommand) -> JobResult:
    job_id = uuid.uuid4().hex[:12]
    output_psd = settings.output_dir / f"{job_id}.psd"
    preview_jpg = settings.preview_dir / f"{job_id}.jpg"

    engine = PsdEngine(template_path)
    changes = engine.apply(cmd)

    if not changes:
        raise HTTPException(400, "No changes to apply")

    engine.save(output_psd)
    logger.info("PSD saved: %s", output_psd)

    generate_preview(output_psd, preview_jpg)
    logger.info("Preview saved: %s", preview_jpg)

    return JobResult(
        job_id=job_id,
        template=template_path.name,
        command=cmd,
        output_psd=str(output_psd),
        preview_jpg=str(preview_jpg),
        changes_applied=changes,
    )
