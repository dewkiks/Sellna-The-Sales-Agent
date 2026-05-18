# sales_agentic_ai/app/agents/__init__.py
"""
Agent layer for the Sellna.ai sales-intelligence pipeline.

This package exposes every pipeline agent through a single import surface so
that the pipeline orchestrator (app/pipelines/sales_pipeline.py) and API
routes can import them without knowing the internal module layout.

Pipeline order (stages run sequentially or as noted):
    1. DomainAgent        — company + market analysis
    2. CompetitorAgent    — LLM-discovered competitor list
    3. WebAgent           — parallel competitor website scraping
    4. SocialAgent        — social accounts / team / contact harvesting
    5. CleaningAgent      — normalise raw scraped data
    6. GapAnalysisAgent   — RAG-powered market-gap discovery
    7. ICPAgent           — Ideal Customer Profile generation
    8. PersonaAgent       — buyer-persona generation (RAG-enriched)
    9. OutreachAgent      — multi-channel outreach copy (RAG-grounded)

OptimizationAgent is a post-pipeline feedback loop rather than a core stage;
it consumes engagement metrics from deployed outreach assets and returns
improvement recommendations.

All agents are stateless: they hold no data between calls so the pipeline
can instantiate them once and call them for any company without risk of
cross-run contamination.
"""

from .domain_agent import DomainAgent
from .competitor_agent import CompetitorAgent
from .web_agent import WebAgent
from .cleaning_agent import CleaningAgent
from .gap_analysis_agent import GapAnalysisAgent
from .icp_agent import ICPAgent
from .persona_agent import PersonaAgent
from .outreach_agent import OutreachAgent
from .optimization_agent import OptimizationAgent
from .social_agent import SocialAgent

__all__ = [
    "DomainAgent",
    "CompetitorAgent",
    "WebAgent",
    "CleaningAgent",
    "GapAnalysisAgent",
    "ICPAgent",
    "PersonaAgent",
    "OutreachAgent",
    "OptimizationAgent",
    "SocialAgent",
]
