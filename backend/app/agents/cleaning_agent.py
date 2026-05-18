"""Data Cleaning Agent — pipeline stage 5.

Normalizes and structures raw web-scraped competitor data before it enters
the vector store and LLM prompts in later stages.

Responsibilities:
- Deduplicates feature strings (word-level) so the LLM does not see the
  same feature listed multiple times with minor phrasing differences.
- Joins and normalizes pricing tier strings into a single readable line.
- Strips residual whitespace and Unicode noise from marketing copy and
  value propositions.
- Assembles a single ``normalized_text`` field (capped at 8 000 chars)
  that is the primary embedding / prompt payload for GapAnalysisAgent.

Design note: this agent is *intentionally* lightweight.  The heavy HTML
stripping and tag removal was already performed by extractor.py inside
the scrapping_module.  CleaningAgent only handles the text-level
normalization needed to make the content safe and compact for LLMs and
vector search.

Pipeline position: receives CompetitorWebData from WebAgent (stage 3),
produces CompetitorCleanData consumed by GapAnalysisAgent (stage 6).

Key dependencies:
  - app.utils.text_cleaning — shared text helpers (clean_text,
    deduplicate_list, normalize_whitespace)
  - app.schemas.competitor — CompetitorWebData / CompetitorCleanData
"""

from __future__ import annotations

import re
import time

from app.core.logging import get_logger
from app.schemas.competitor import CompetitorCleanData, CompetitorWebData
from app.utils.text_cleaning import (
    clean_text,
    deduplicate_list,
    normalize_whitespace,
)

logger = get_logger(__name__)


class CleaningAgent:
    """Stateless data cleaning / normalization agent.

    Has no constructor dependencies — it uses only pure utility functions so
    it can be instantiated with zero configuration.
    """

    async def run(self, web_data_list: list[CompetitorWebData]) -> list[CompetitorCleanData]:
        """Clean and normalize a list of raw scraped competitor records.

        Processes every item synchronously (CPU-bound text ops, not I/O) and
        returns one CleanData record per input record.

        Args:
            web_data_list: Raw structured data returned by WebAgent.

        Returns:
            Parallel list of CompetitorCleanData ready for embedding / LLM use.
        """
        t0 = time.perf_counter()
        logger.info(
            "cleaning_agent.start",
            module_name="CleaningAgent",
            input_summary=f"items={len(web_data_list)}",
        )

        cleaned = [self._clean_one(wd) for wd in web_data_list]

        elapsed = time.perf_counter() - t0
        logger.info(
            "cleaning_agent.complete",
            module_name="CleaningAgent",
            execution_time=round(elapsed, 3),
            output_summary=f"cleaned={len(cleaned)} records",
        )
        return cleaned

    @staticmethod
    def _clean_one(wd: CompetitorWebData) -> CompetitorCleanData:
        """Normalize a single scraped competitor record.

        Applies text cleaning and deduplication to every structured field, then
        assembles ``normalized_text``, which is the concatenated, capped blob
        used for vector embedding and LLM prompts downstream.

        Args:
            wd: Raw CompetitorWebData from WebAgent.

        Returns:
            CompetitorCleanData with all fields cleaned and normalized_text built.
        """
        # Clean features
        clean_features = deduplicate_list([
            clean_text(f) for f in wd.features if clean_text(f)
        ])

        # Clean pricing
        pricing_raw = " | ".join(wd.pricing_tiers) if wd.pricing_tiers else ""
        clean_pricing = normalize_whitespace(clean_text(pricing_raw))

        # Clean positioning
        clean_positioning = normalize_whitespace(clean_text(wd.marketing_copy))

        # Clean value proposition
        clean_vp = normalize_whitespace(clean_text(wd.value_proposition))

        # Build full normalized text for embedding.
        # Order: value-prop → positioning → top features → raw paragraphs.
        # Capping features at 10 and paragraphs at 20 prevents the embedding
        # from being dominated by one extremely verbose competitor page.
        all_paragraphs = [clean_text(p) for p in wd.raw_paragraphs if clean_text(p)]
        normalized_text = "\n".join(
            [clean_vp, clean_positioning] + clean_features[:10] + all_paragraphs[:20]
        )
        # Collapse runs of blank lines left by empty cleaned fields.
        normalized_text = re.sub(r"\n{3,}", "\n\n", normalized_text).strip()

        return CompetitorCleanData(
            competitor_id=wd.competitor_id,
            clean_features=clean_features,
            clean_pricing=clean_pricing,
            clean_positioning=clean_positioning,
            clean_value_proposition=clean_vp,
            # Hard cap at 8 000 chars: safe for both Qdrant embedding models
            # (typical 512-token limit) and LLM context windows.
            normalized_text=normalized_text[:8000],
        )
