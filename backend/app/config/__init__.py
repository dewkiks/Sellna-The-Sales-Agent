# sales_agentic_ai/app/config/__init__.py
"""
app/config — Application configuration package.

Re-exports the two primary symbols from settings.py so that any module in
the project can simply write:

    from app.config import Settings, get_settings

rather than referencing the full sub-module path.
"""
from .settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
