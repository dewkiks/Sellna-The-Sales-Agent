# sales_agentic_ai/app/api/__init__.py
"""
app/api — HTTP API package for Sellna.ai.

This package contains:
  - router.py : The central APIRouter that aggregates all v1 sub-routers.
                It is registered on the FastAPI app in main.py under the
                /api/v1 prefix.
  - v1/       : One module per domain area (company, competitors, icp,
                personas, outreach, analytics, pipeline, dashboard,
                scrapers, ui).  Each module owns its own APIRouter and
                is imported/included by router.py.
"""
