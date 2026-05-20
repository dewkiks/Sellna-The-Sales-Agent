"""Gap Analysis Agent — pipeline stage 6 (first RAG stage).

The first agent in the pipeline that uses Retrieval-Augmented Generation
(RAG).  It identifies concrete market gaps the analyzed company can exploit
by reasoning over real competitor content retrieved from the Qdrant vector
store.

RAG flow:
  1. Index — each CompetitorCleanData.normalized_text is chunked into
     ~2 500-char overlapping segments and upserted into a per-run Qdrant
     collection named ``gap_<company_id>``.
  2. Retrieve — a gap-discovery query (derived from the company's pain points
     and strengths) fetches the top-3 semantically closest chunks.
  3. Generate — the retrieved chunks are injected into the LLM system prompt
     alongside the gap-analysis instruction, grounding the output in actual
     competitor language rather than LLM hallucination.

Gap types classified:
  - ``missing_feature``      — feature competitors lack or handle poorly
  - ``underserved_segment``  — buyer group poorly addressed by incumbents
  - ``messaging_weakness``   — angle competitors fail to communicate clearly

Pipeline position: receives CompanyAnalysis (stage 1) + CompetitorCleanData
list (stage 5), produces MarketGap list consumed by ICPAgent (stage 7).

Key dependencies:
  - app.services.rag_service — Qdrant index + retrieval + LLM orchestration
  - app.services.llm_service — underlying LLM client (via RAGService)
  - app.utils.json_parse — robust LLM JSON extraction / repair
  - app.schemas.gap_analysis — MarketGap Pydantic model
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from uuid import UUID

from app.core.logging import get_logger
from app.schemas.company import CompanyAnalysis
from app.schemas.competitor import CompetitorCleanData
from app.schemas.gap_analysis import MarketGap
from app.services.llm_service import get_llm_service
from app.services.rag_service import RAGService
from app.utils.json_parse import parse_llm_json

logger = get_logger(__name__)

_SYSTEM_GAP = """You are a B2B competitive-intelligence analyst.
Using the competitor intelligence context and the company details provided,
identify concrete market gaps the company can exploit. Combine the context with
your own knowledge of the market where the context is thin.

Return a JSON object:
{
  "gaps": [
    {
      "gap_type": "missing_feature | underserved_segment | messaging_weakness",
      "description": "What the gap is",
      "opportunity": "How the company can exploit this gap",
      "confidence_score": 0.0-1.0,
      "supporting_evidence": ["evidence1", "evidence2"],
      "recommended_action": "Specific action to take"
    }
  ]
}
Identify 2-4 gaps. Respond with ONLY valid JSON — no markdown, no code fences, no explanation."""


class GapAnalysisAgent:
    """RAG-powered gap analysis over competitor landscape.

    Holds a RAGService (which wraps Qdrant + the LLM) and a bare LLM client
    as instance attributes.  Both are singletons under the hood, so multiple
    pipeline runs share the same network connections.
    """

    def __init__(self) -> None:
        self._rag = RAGService()
        self._llm = get_llm_service()

    async def run(
        self,
        analysis: CompanyAnalysis,
        clean_data_list: list[CompetitorCleanData],
        stream_cb: Callable[[dict], None] | None = None,
    ) -> list[MarketGap]:
        """Identify market gaps by RAG-querying competitor intelligence.

        Args:
            analysis: CompanyAnalysis from DomainAgent — used to build the
                      gap query and the ``gap_<company_id>`` collection name.
            clean_data_list: Normalized competitor records from CleaningAgent.
            stream_cb: Optional callback receiving SSE-style ``token`` /
                ``reasoning`` events so the frontend Token output panel
                shows chunking, embedding, retrieval and LLM progress live.

        Returns:
            List of MarketGap objects (typically 2–4), each with a type,
            description, opportunity, confidence score, supporting evidence,
            and recommended action.  Empty list if RAG returns no usable data.
        """
        t0 = time.perf_counter()
        company_id = analysis.company_id
        collection = f"gap_{company_id}"

        def emit(line: str) -> None:
            if stream_cb:
                stream_cb({"type": "token", "content": line})

        logger.info(
            "gap_analysis_agent.start",
            module_name="GapAnalysisAgent",
            company=analysis.company_name,
            input_summary=f"competitor_docs={len(clean_data_list)}",
        )

        emit(
            f"→ Gap analysis for {analysis.company_name}\n"
            f"  collection: {collection}\n"
            f"  input docs: {len(clean_data_list)}\n\n"
        )

        # ---- Index: chunk and upsert competitor text into Qdrant ----
        # Chunk size 2 500 chars with a 200-char trailing overlap prevents a
        # relevant sentence from being split right at a chunk boundary.
        # Per-run collection (gap_<company_id>) isolates competitors across
        # concurrent pipeline executions.
        documents = []
        for cd in clean_data_list:
            text = cd.normalized_text.strip()
            if not text:
                continue
            chunk_size = 2500
            for i in range(0, len(text), chunk_size):
                documents.append(text[i : i + chunk_size + 200])
        total_chars = sum(len(d) for d in documents)
        emit(
            f"→ Chunking competitor text → {len(documents)} chunks "
            f"({total_chars} chars total, ~2500/chunk)\n"
        )
        if documents:
            emit(f"→ Embedding & indexing into Qdrant collection '{collection}'...\n")
            t_idx = time.perf_counter()
            await self._rag.index_documents(collection, documents)
            emit(
                f"✓ Indexed {len(documents)} chunks in "
                f"{round(time.perf_counter() - t_idx, 2)}s\n\n"
            )
        else:
            emit("⚠ No documents to index — gap analysis will rely on LLM priors only\n\n")

        # ---- Query: single broad RAG call covers all three gap types ----
        # One query (rather than three separate ones) is a deliberate latency
        # trade-off: the LLM system prompt instructs the model to categorise
        # each gap itself, keeping the Qdrant round-trips to one.
        company_context = self._build_context(analysis)

        gap_query = (
            f"What features, segments, and messaging angles are missing from the market?\n"
            f"Company context: {company_context}"
        )

        emit(
            f"→ Retrieving top-3 chunks for gap query\n"
            f"→ Asking model to identify 2–4 gaps from retrieved context...\n\n"
        )

        def on_token(t: str) -> None:
            if stream_cb:
                stream_cb({"type": "token", "content": t})

        def on_reasoning(t: str) -> None:
            if stream_cb:
                stream_cb({"type": "reasoning", "content": t})

        raw = await self._rag.query(
            collection=collection,
            question=gap_query,
            system_prompt=_SYSTEM_GAP,
            top_k=3,
            json_mode=True,
            on_token=on_token,
            on_reasoning=on_reasoning,
        )

        data = parse_llm_json(raw)
        gaps: list[MarketGap] = []

        for item in data.get("gaps", []):
            try:
                gap = MarketGap(
                    company_id=company_id,
                    gap_type=item.get("gap_type", "missing_feature"),
                    description=item.get("description", ""),
                    opportunity=item.get("opportunity", ""),
                    confidence_score=float(item.get("confidence_score", 0.5)),
                    supporting_evidence=item.get("supporting_evidence", []),
                    recommended_action=item.get("recommended_action", ""),
                )
                gaps.append(gap)
            except Exception as e:
                logger.warning("gap_analysis_agent.parse_error", error=str(e))

        elapsed = time.perf_counter() - t0
        logger.info(
            "gap_analysis_agent.complete",
            module_name="GapAnalysisAgent",
            execution_time=round(elapsed, 3),
            output_summary=f"gaps={len(gaps)}",
        )
        return gaps

    @staticmethod
    def _build_context(analysis: CompanyAnalysis) -> str:
        """Serialize the key discriminating facts from CompanyAnalysis.

        This string is appended to the RAG query so the vector search returns
        chunks most relevant to *this specific company's* competitive context,
        not just generic competitor text.

        Args:
            analysis: DomainAgent output.

        Returns:
            Single-line context string injected into the RAG query.
        """
        return (
            f"Company: {analysis.company_name}. "
            f"Category: {analysis.product_category}. "
            f"Market: {getattr(analysis.market_type, 'value', analysis.market_type)}. "
            f"Pain points: {', '.join(analysis.pain_points[:4])}. "
            f"Features strengths: {', '.join(analysis.strengths[:4])}. "
            f"Weaknesses: {', '.join(analysis.weaknesses[:3])}."
        )
