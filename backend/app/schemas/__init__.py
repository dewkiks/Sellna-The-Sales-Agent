# sales_agentic_ai/app/schemas/__init__.py
"""Schemas package — re-exports the most commonly used Pydantic v2 models.

Importing from ``app.schemas`` (rather than from individual sub-modules)
gives callers a single stable import path and makes it easy to see which
models are part of the "public" data contract of the application.
"""
from .company import CompanyInput, CompanyAnalysis
from .competitor import CompetitorDiscovered, CompetitorWebData, CompetitorCleanData
from .icp import ICPProfile, ICPGenerateRequest
from .persona import BuyerPersona, PersonaGenerateRequest
from .outreach import OutreachAsset, OutreachGenerateRequest, OutreachFeedback
from .gap_analysis import MarketGap

__all__ = [
    "CompanyInput", "CompanyAnalysis",
    "CompetitorDiscovered", "CompetitorWebData", "CompetitorCleanData",
    "ICPProfile", "ICPGenerateRequest",
    "BuyerPersona", "PersonaGenerateRequest",
    "OutreachAsset", "OutreachGenerateRequest", "OutreachFeedback",
    "MarketGap",
]
