# app/schemas — Pydantic Data Contracts

The `schemas` package defines every Pydantic v2 model used as a data contract
between pipeline agents, API routes, and the database layer.  Each model
represents either user input, an agent's structured output, or a request/response
body for an API endpoint.  Validation (field types, value ranges, required vs
optional) is enforced automatically by Pydantic before any agent logic runs.

## Files

| File | Description |
|---|---|
| `__init__.py` | Re-exports the most-used schemas as a stable public API for the package. |
| `company.py` | `CompanyInput` (user-submitted pipeline entry point) and `CompanyAnalysis` (Domain Agent output). |
| `competitor.py` | `CompetitorDiscovered`, `CompetitorWebData`, `CompetitorCleanData` — three stages of competitor enrichment. |
| `gap_analysis.py` | `MarketGap` — one discovered competitive opportunity or market gap. |
| `icp.py` | `ICPProfile` (Ideal Customer Profile) and `ICPGenerateRequest` (API trigger). |
| `outreach.py` | `OutreachAsset`, `OutreachGenerateRequest`, `OutreachUpdateRequest`, `OutreachFeedback`. |
| `persona.py` | `BuyerPersona` (individual buyer within an ICP company) and `PersonaGenerateRequest`. |
| `social.py` | `SocialProfileData`, `PersonContact`, `SubjectSocials`, `SocialIntelligenceOutput` — social scraping results. |

## Architecture fit

```
User POST /company/analyze   (CompanyInput)
        |
        v
  Domain Agent        --> CompanyAnalysis
        |
  Competitor Agent    --> [CompetitorDiscovered, ...]
        |
  Web Agent           --> [CompetitorWebData, ...]
        |
  Cleaning Agent      --> [CompetitorCleanData, ...]
        |
  Gap Analysis Agent  --> [MarketGap, ...]
        |
  ICP Agent           --> [ICPProfile, ...]
        |
  Persona Agent       --> [BuyerPersona, ...]
        |
  Outreach Agent      --> [OutreachAsset, ...]
```

Schemas flow through the pipeline as Python objects; before being stored they
are serialised to `dict` (via `.model_dump()`) and written into JSONB columns
by the repository layer.  API routes return schemas directly as JSON responses.

Schemas are **separate** from ORM models by design: Pydantic validates data at
the boundary (API + agent output); SQLAlchemy manages the DB mapping.  Mixing
them would couple validation logic to persistence logic.

## Likely exam questions

**Q: Why does the project have both Pydantic schemas and SQLAlchemy ORM models?**
A: They serve different purposes. Pydantic schemas validate and serialise data at API boundaries and between agents — they enforce field types, ranges, and required fields. SQLAlchemy ORM models map Python classes to database tables and handle query generation. Mixing them would couple validation to persistence, making both harder to change.

**Q: How are enumerated fields (like `PricingModel`) enforced in the API?**
A: They use Python `str, Enum` subclasses. Pydantic rejects any value not in the enum at parse time, so invalid strings never reach agent code. Because they inherit from `str`, they serialise to JSON without needing `.value`.

**Q: What is the difference between `ICPProfile` and `BuyerPersona`?**
A: An `ICPProfile` describes a *company* (industry, size, revenue range, buying signals). A `BuyerPersona` describes an *individual* inside such a company (title, goals, objections, preferred channels). The Persona Agent refines each ICP into one or more personas so outreach can be personalised to specific roles.

**Q: What does `CompanyAnalysis.raw_input` store and why?**
A: It embeds the original `CompanyInput` inside the analysis object. This means downstream agents always have full context in a single object without needing to fetch the original input separately from the database.

**Q: How does `OutreachFeedback` close the feedback loop?**
A: It carries `open_rate`, `reply_rate`, and `conversion_rate` back to the API after a campaign runs. The `OutreachRepository.update_feedback()` writes these into the `outreach_assets` table so the data can be used to rank or re-generate outreach content.

**Q: Why does `SocialIntelligenceOutput` group results under `subjects` rather than a flat list?**
A: Each subject (the target company or a competitor) has its own set of social profiles, people, emails, and phones. Grouping by subject preserves the attribution — agents and the frontend need to know which profiles belong to which company or competitor.
