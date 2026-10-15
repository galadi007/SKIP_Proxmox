"""Erzeugt cluster.png -- Regenerieren mit `make docs-diagrams`."""

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.k8s.compute import Deployment
from diagrams.k8s.network import Ingress, Service
from diagrams.k8s.storage import PVC
from diagrams.onprem.client import User

OUT = Path(__file__).parent / "cluster"

with Diagram(
    "SKIP Plattform auf k3d",
    filename=str(OUT),
    outformat="png",
    show=False,
    direction="LR",
    graph_attr={"fontname": "Merriweather Sans", "bgcolor": "transparent"},
):
    user = User("Nutzer")

    with Cluster("k3d skip-local"):
        ingress = Ingress("Traefik\n:8080 / :8443")

        with Cluster("platform-system"):
            web = Deployment("skip-web")
            api = Deployment("skip-api")
            litellm = Deployment("litellm")
            minio = Deployment("minio")

        with Cluster("kro"):
            kro = Deployment("kro-controller")

        with Cluster("team-data (Tenant)"):
            app_svc = Service("app")
            app = Deployment("App-Instanz\n(z.B. OpenWebUI)")
            pvc = PVC("data")

    user >> ingress
    ingress >> Edge(label="localhost") >> web
    ingress >> Edge(label="api.localhost") >> api
    web >> api
    kro >> Edge(style="dashed", label="reconciled") >> app
    app_svc >> app
    app >> pvc
    app >> Edge(label="llm-Capability") >> litellm
