from contextlib import asynccontextmanager

from fastapi import FastAPI
from kubernetes import config

from auth.api import router as auth_router
from deploy.api import router as deploy_router
from storage.api import router as storage_router
from teams.api import router as teams_router
from templates.api import router as templates_router


def _load_kubernetes_config() -> None:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _load_kubernetes_config()
    yield


app = FastAPI(
    title="SKIP platform backend",
    version="0.3.0",
    description=(
        "Skip platform backend: deploys KRO-managed application templates, "
        "authenticates users via Authentik (OIDC) and manages app sharing."
    ),
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(templates_router)
app.include_router(deploy_router)
app.include_router(storage_router)
app.include_router(teams_router)



@app.get("/healthz", tags=["Status"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}
