# sales_agentic_ai/app/api/v1/__init__.py
"""
app/api/v1 — versioned API sub-package.

Each module in this directory owns one FastAPI APIRouter.
router.py (one level up) imports them all and merges them into the
single `api_router` that main.py registers under /api/v1.
"""
