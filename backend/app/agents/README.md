# app/agents — Sellna.ai Agent Layer

## Purpose

This folder contains every AI agent that makes up the Sellna.ai sales-intelligence pipeline.
Each agent is a single Python class with an async `run()` method.
Together they form a sequential nine-stage pipeline that converts a user-supplied company description into competitor analysis, market gaps, Ideal Customer Profiles, buyer personas, and personalized outreach copy.

---

## File Descriptions

| File | Description |
|---|---|
| `__init__.py` | Re-exports all agent classes so the pipeline can `from app.agents import DomainAgent, ...` without knowing internal module paths. |
| `domain_agent.py` | **Stage 1.** Accepts raw `CompanyInput`, calls the LLM (temp 0.2) to classify market type and produce buyer roles, segments, pain points, and positioning. Emits SSE streaming events. |
| `competitor_agent.py` | **Stage 2.** Uses LLM world-knowledge (temp 0.3) to identify 3–5 real named competitors, each categorized as Direct / Indirect / Alternative with a relevance score. |
| `web_agent.py` | **Stage 3.** Scrapes all competitor homepages in parallel via `asyncio.gather`; extracts features, pricing, marketing copy, and value proposition using keyword heuristics. Retries on 404 with the bare domain. |
| `social_agent.py` | **Stage 4.** Crawls a subject's homepage + team/about/contact pages to harvest LinkedIn/Instagram org accounts, real team members (via JSON-LD, `/in/` links, team-card headings), emails, and phone numbers. No LLM — pure HTML parsing. |
| `cleaning_agent.py` | **Stage 5.** Pure text normalization: deduplicates features, normalizes pricing/positioning, and assembles a single `normalized_text` blob (≤ 8 000 chars) per competitor ready for embedding. No LLM or I/O. |
| `gap_analysis_agent.py` | **Stage 6 — first RAG stage.** Indexes competitor `normalized_text` into a per-run Qdrant collection, then queries it (top-k=3) with a gap-discovery prompt to identify missing features, underserved segments, and messaging weaknesses. |
| `icp_agent.py` | **Stage 7.** Generates `num_profiles` Ideal Customer Profiles using `CompanyAnalysis` + the `MarketGap` list. LLM infers concrete company demographics (size, revenue, tech stack) that are not in the structured inputs. Emits SSE events. |
| `persona_agent.py` | **Stage 8 — RAG-powered.** Generates buyer personas for each ICP in parallel (one asyncio task per ICP). Queries the same Qdrant gap collection to ground persona pain points and objections in real competitor messaging. |
| `outreach_agent.py` | **Stage 9 — final stage, RAG-powered.** Generates cold email, LinkedIn message, and call opener script for each persona in parallel (one LLM call per channel, all concurrent). Temperature 0.6 — highest in the pipeline — for natural-sounding copy. |
| `optimization_agent.py` | **Post-pipeline feedback loop.** Joins outreach assets with engagement metrics (open/reply/conversion rates), passes a compact performance table to the LLM (temp 0.2), and returns scored optimization recommendations. Not part of the sequential pipeline. |

---

## Pipeline Stages, RAG Usage, and Scraping

```
Stage  Agent               RAG?   Scraping?   Notes
-----  ------------------  -----  ----------  -----------------------------------
1      DomainAgent         No     No          LLM market analysis from user input
2      CompetitorAgent     No     No          LLM world-knowledge competitor discovery
3      WebAgent            No     Yes         Parallel HTTP/Playwright homepage scrape
4      SocialAgent         No     Yes         Multi-page crawl + HTML parsing
5      CleaningAgent       No     No          Pure text normalization (CPU only)
6      GapAnalysisAgent    Yes    No          Qdrant index + query → LLM gap analysis
7      ICPAgent            No     No          LLM ICP generation from gaps + analysis
8      PersonaAgent        Yes    No          Qdrant query → LLM persona generation
9      OutreachAgent       Yes    No          Qdrant retrieve → parallel LLM copy gen
-      OptimizationAgent   No     No          Feedback loop, called on demand
```

The RAG collection (`gap_<company_id>`) is created by GapAnalysisAgent in stage 6
and reused by PersonaAgent (stage 8) and OutreachAgent (stage 9).
This means all three RAG stages share the same competitor intelligence index built from
the cleaned scrape data — no re-indexing is needed.

---

## Likely Exam Questions

**Q1: Why are all agents stateless?**
A: Stateless means no run-specific data is stored on the instance between calls.
This allows the pipeline to instantiate each agent once (at startup) and call it
for any company without risk of data leaking between concurrent pipeline runs.
It also makes the agents trivially testable — pass in a mock LLM, call `run()`, inspect the output.

**Q2: How does an agent recover when the LLM returns malformed JSON?**
A: Every agent calls `parse_llm_json(raw)` (from `app/utils/json_parse.py`) which
strips Markdown code fences, handles leading/trailing text, and attempts JSON repair
before raising. If individual items in the parsed array fail Pydantic validation,
the `except Exception` block inside the `for item in data.get(...)` loop logs a
warning and skips that item — the agent never crashes the whole pipeline over one
bad entry.

**Q3: Which agents use RAG and why?**
A: GapAnalysisAgent (stage 6), PersonaAgent (stage 8), and OutreachAgent (stage 9).
RAG is used when the LLM needs to reason *specifically* about the competitor landscape
that was actually scraped — not generic industry knowledge.
- GapAnalysisAgent needs real competitor feature text to identify what is missing.
- PersonaAgent grounds buyer pain points in what competitors actually say about their buyers.
- OutreachAgent grounds copy claims in real competitive differentiators so messages
  do not make generic claims that prospects can easily rebut.

**Q4: Why does OutreachAgent use a higher temperature (0.6) than DomainAgent (0.2)?**
A: Temperature controls randomness. DomainAgent classifies a market — a factual task
where a stable, repeatable answer is desirable (low temp). OutreachAgent writes sales
copy — a creative task where different personas must get genuinely different messages
that sound human-written, not formulaic (higher temp). Setting it too low would produce
identical-sounding emails for every persona.

**Q5: How does WebAgent handle a competitor URL that returns a 404?**
A: After the initial scrape fails with a 404 error, `scrape_one()` checks whether
the URL has a non-root path (e.g. `/crm`). If so, it strips the path and retries with
just the scheme + domain (e.g. `https://hubspot.com`). This handles the common case
where the LLM generates a product sub-page URL instead of the homepage.

**Q6: What three strategies does SocialAgent use to discover team members, and why are they ranked?**
A: 
1. **JSON-LD Person schema** — most reliable; structured machine-readable data from schema.org markup.
2. **LinkedIn `/in/` anchor links** — strong signal because a person's own LinkedIn profile URL is authoritative.
3. **Team-card name headings** — heuristic, lowest confidence; restricted to pages whose URL contains team/leadership path segments to avoid false positives from product names and marketing headlines on homepages.

**Q7: Why is GapAnalysisAgent's competitor text chunked into ~2 500-character segments with 200-char overlap before indexing?**
A: Vector embedding models have a fixed token limit (typically 512 tokens ≈ ~2 000 chars).
Text longer than this limit is truncated, so long competitor pages must be split.
The 200-char trailing overlap prevents a key sentence that falls at a chunk boundary
from being split across two chunks and missing the relevant context in a retrieval hit.
