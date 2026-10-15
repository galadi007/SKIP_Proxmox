from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth.oidc import get_current_user

from .dtos import TemplateDetails, TemplateReloadResult, TemplateSummary
from .errors import (
    InvalidTemplateError,
    TemplateAssetNotFoundError,
    TemplateNotFoundError,
)
from .service import AbstractTemplateService, FileSystemTemplateService
from .sources import load_template_loaders_from_env


@lru_cache
def get_template_service() -> AbstractTemplateService:
    default_root = Path(__file__).resolve().parents[3] / "templates"
    return FileSystemTemplateService(load_template_loaders_from_env(default_root))


router = APIRouter(
    prefix="/api/templates",
    tags=["Templates"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[TemplateSummary])
def list_templates(
    service: AbstractTemplateService = Depends(get_template_service),
) -> list[TemplateSummary]:
    return service.list()


@router.post("/reload", response_model=TemplateReloadResult)
def reload_templates(
    service: AbstractTemplateService = Depends(get_template_service),
) -> TemplateReloadResult:
    return service.reload()


@router.get("/{name}", response_model=TemplateDetails)
def template_details(
    name: str,
    service: AbstractTemplateService = Depends(get_template_service),
) -> TemplateDetails:
    try:
        return service.get(name)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{name}/schema")
def template_schema(
    name: str,
    service: AbstractTemplateService = Depends(get_template_service),
) -> dict:
    try:
        details = service.get(name)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"schema": details.configuration_schema, "formHints": details.form_hints}


@router.get("/{name}/logo", response_class=FileResponse)
def template_logo(
    name: str,
    service: AbstractTemplateService = Depends(get_template_service),
) -> FileResponse:
    try:
        asset = service.get_logo(name)
    except (TemplateNotFoundError, TemplateAssetNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidTemplateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(asset.path, media_type=asset.media_type)


@router.get("/{name}/assets/{asset_path:path}", response_class=FileResponse)
def template_asset(
    name: str,
    asset_path: str,
    service: AbstractTemplateService = Depends(get_template_service),
) -> FileResponse:
    try:
        asset = service.get_asset(name, asset_path)
    except (TemplateNotFoundError, TemplateAssetNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidTemplateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(asset.path, media_type=asset.media_type)
