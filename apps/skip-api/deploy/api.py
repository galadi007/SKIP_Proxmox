from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Response

from auth.authentik import get_authentik_client
from auth.dtos import AuthenticatedUser
from auth.entitlements import EntitlementExceededError, get_entitlement_provider
from auth.oidc import get_current_user
from auth.service import configured_namespaces
from templates.api import get_template_service
from templates.errors import TemplateNotFoundError

from .dtos import AddMemberRequest, AppMembers, DeployRequest, Deployment
from .errors import (
    DeploymentConflictError,
    DeploymentForbiddenError,
    DeploymentNotFoundError,
    InvalidDeploymentError,
)
from .render import get_apps_url_settings
from .service import KubernetesDeployService

EXPECTED_ERRORS = (
    EntitlementExceededError,
    TemplateNotFoundError,
    DeploymentNotFoundError,
    DeploymentForbiddenError,
    DeploymentConflictError,
    InvalidDeploymentError,
)


@lru_cache
def get_deploy_service() -> KubernetesDeployService:
    return KubernetesDeployService(
        get_template_service(),
        configured_namespaces(),
        authentik=get_authentik_client(),
        entitlements=get_entitlement_provider(),
        urls=get_apps_url_settings(),
    )


router = APIRouter(prefix="/api/apps", tags=["Applications"])


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (TemplateNotFoundError, DeploymentNotFoundError)):
        return HTTPException(404, str(exc))
    if isinstance(exc, (DeploymentForbiddenError, EntitlementExceededError)):
        return HTTPException(403, str(exc))
    if isinstance(exc, DeploymentConflictError):
        return HTTPException(409, str(exc))
    return HTTPException(422, str(exc))


@router.post("", status_code=201, response_model=Deployment)
def deploy(
    request: DeployRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: KubernetesDeployService = Depends(get_deploy_service),
) -> Deployment:
    try:
        return service.deploy(request, user)
    except EXPECTED_ERRORS as exc:
        raise _translate_error(exc) from exc


@router.get("", response_model=list[Deployment])
def list_deployments(
    user: AuthenticatedUser = Depends(get_current_user),
    service: KubernetesDeployService = Depends(get_deploy_service),
) -> list[Deployment]:
    return service.list(user)


@router.get("/{template}/{namespace}/{name}", response_model=Deployment)
def deployment_status(
    template: str,
    namespace: str,
    name: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: KubernetesDeployService = Depends(get_deploy_service),
) -> Deployment:
    try:
        return service.get(template, namespace, name, user)
    except EXPECTED_ERRORS as exc:
        raise _translate_error(exc) from exc


@router.delete("/{template}/{namespace}/{name}", status_code=204)
def delete_deployment(
    template: str,
    namespace: str,
    name: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: KubernetesDeployService = Depends(get_deploy_service),
) -> Response:
    try:
        service.delete(template, namespace, name, user)
    except EXPECTED_ERRORS as exc:
        raise _translate_error(exc) from exc
    return Response(status_code=204)


@router.get("/{template}/{namespace}/{name}/members", response_model=AppMembers)
def list_members(
    template: str,
    namespace: str,
    name: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: KubernetesDeployService = Depends(get_deploy_service),
) -> AppMembers:
    """Mitglieder der Authentik-Gruppe `app-<namespace>-<name>`."""
    try:
        return service.list_members(template, namespace, name, user)
    except EXPECTED_ERRORS as exc:
        raise _translate_error(exc) from exc


@router.post("/{template}/{namespace}/{name}/members", response_model=AppMembers)
def add_member(
    template: str,
    namespace: str,
    name: str,
    body: AddMemberRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: KubernetesDeployService = Depends(get_deploy_service),
) -> AppMembers:
    """App mit einem weiteren Benutzer teilen (nur Owner/Admin)."""
    try:
        return service.add_member(template, namespace, name, body.username, user)
    except EXPECTED_ERRORS as exc:
        raise _translate_error(exc) from exc


@router.delete(
    "/{template}/{namespace}/{name}/members/{username}", response_model=AppMembers
)
def remove_member(
    template: str,
    namespace: str,
    name: str,
    username: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: KubernetesDeployService = Depends(get_deploy_service),
) -> AppMembers:
    """Freigabe fuer einen Benutzer entziehen (nur Owner/Admin)."""
    try:
        return service.remove_member(template, namespace, name, username, user)
    except EXPECTED_ERRORS as exc:
        raise _translate_error(exc) from exc
