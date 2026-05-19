"""Central API router — mounts all v1 sub-routers.

This module is the single assembly point for the entire REST API.
main.py registers `api_router` on the FastAPI application under the
`/api/v1` prefix, so every route defined in the v1 sub-modules is
reachable at `/api/v1/<sub-module-prefix>/<path>`.

Adding a new domain area requires only:
  1. Creating a new module in app/api/v1/ with its own `router`.
  2. Importing it here and calling `api_router.include_router(...)`.
"""

from fastapi import APIRouter

from app.api.v1 import analytics, auth, chat, company, competitors, dashboard, icp, outreach, personas, pipeline, scrapers, ui

# ---- Root router — no prefix here; the /api/v1 prefix is applied in main.py ----
api_router = APIRouter()

# Each include_router call merges the sub-module's routes into api_router.
# The sub-module's own `prefix` (e.g. "/company", "/pipeline") is preserved.
api_router.include_router(auth.router)
api_router.include_router(company.router)
api_router.include_router(competitors.router)
api_router.include_router(icp.router)
api_router.include_router(personas.router)
api_router.include_router(outreach.router)
api_router.include_router(analytics.router)
api_router.include_router(pipeline.router)
api_router.include_router(dashboard.router)
api_router.include_router(scrapers.router)
api_router.include_router(chat.router)
api_router.include_router(ui.router)
