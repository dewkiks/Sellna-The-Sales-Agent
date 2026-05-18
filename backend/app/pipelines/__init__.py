# sales_agentic_ai/app/pipelines/__init__.py
"""
Pipelines package — top-level orchestration of the multi-agent workflow.

Exports:
    SalesPipeline  — async orchestrator that sequences all 9 agent stages.
    PipelineResult — dataclass representing the complete enterprise output
                     produced by one full pipeline run.

Consumers: FastAPI route handlers in app/api/v1/pipeline.py import
``SalesPipeline`` from here and pass it a DB session + optional callbacks.
"""
from .sales_pipeline import SalesPipeline, PipelineResult

__all__ = ["SalesPipeline", "PipelineResult"]
