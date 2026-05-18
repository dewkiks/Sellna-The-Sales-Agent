"""UI Configuration API — server-driven content for the React frontend.

All endpoints in this module return static JSON configuration rather than
running agents or touching the database.  The design principle is that the
frontend contains zero hardcoded display strings or data structures: nav
labels, feature bullet points, form dropdown options, and marketing copy all
come from here.  This makes content changes deployable without a frontend
rebuild.

Endpoints:
  GET /ui/landing         — landing page hero, features, metrics, workflow.
  GET /ui/company-input   — wizard step definitions and dropdown options
                            for the company input form.
  GET /ui/auth-copy       — login/signup marketing copy.
  GET /ui/personas        — section configuration for the personas page
                            (goals, pain points, objections, triggers).
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/ui", tags=["UI Config"])


@router.get("/landing", summary="Landing page content configuration")
async def get_landing_config() -> dict:
    """GET /ui/landing

    Returns all content for the public landing page: hero text, feature
    cards, social-proof metrics, workflow steps, and footer copy.
    Keeping this in the backend means marketing copy can be A/B tested or
    updated without touching the frontend build.
    """
    return {
        "hero_badge": "Now in Public Beta — Join 200+ teams",
        "hero_title_lines": ["Your AI-Powered", "Sales Intelligence", "Command Center"],
        "hero_subtitle": (
            "From company research to personalized outreach — automate your entire "
            "sales pipeline with autonomous AI agents that think, analyze, and act."
        ),
        "features": [
            {
                "icon": "Target",
                "title": "Competitor Intelligence",
                "desc": "Auto-discover and analyze competitors with AI-powered web scraping and gap analysis.",
            },
            {
                "icon": "Users",
                "title": "ICP & Persona Engine",
                "desc": "Generate ideal customer profiles and buyer personas backed by real market data.",
            },
            {
                "icon": "Sparkles",
                "title": "AI Outreach Generator",
                "desc": "Craft hyper-personalized emails, LinkedIn messages, and call scripts at scale.",
            },
            {
                "icon": "BarChart3",
                "title": "Performance Analytics",
                "desc": "Track open rates, replies, and conversions with real-time optimization feedback.",
            },
            {
                "icon": "Shield",
                "title": "Enterprise Security",
                "desc": "SOC 2 ready architecture with role-based access and encrypted data pipelines.",
            },
            {
                "icon": "Globe",
                "title": "Multi-Market Support",
                "desc": "Target across geographies with localized messaging and regional competitor mapping.",
            },
        ],
        "metrics": [
            {"value": "3.2x", "label": "Higher Reply Rates"},
            {"value": "67%", "label": "Faster Pipeline"},
            {"value": "10k+", "label": "Personas Generated"},
            {"value": "98%", "label": "Data Accuracy"},
        ],
        "workflow_steps": [
            "Enter your company details and product information",
            "AI agents analyze your domain and discover competitors",
            "Gap analysis identifies market opportunities",
            "ICPs and buyer personas are generated automatically",
            "Personalized outreach content is crafted for each persona",
        ],
        "hero_visual_labels": [
            "Domain Analysis",
            "Gap Detection",
            "ICP Generation",
            "Persona Engine",
            "Outreach AI",
            "Analytics",
        ],
        "app_name": "Sales Agentic AI",
        "footer_notice": "© 2026 Sales Agentic AI. All rights reserved.",
    }


@router.get("/company-input", summary="Company input page step configuration")
async def get_company_input_config() -> dict:
    """GET /ui/company-input

    Returns configuration for the multi-step company-input wizard:
      - steps       : step ids, labels, and icons for the progress indicator.
      - select_options : dropdown values for customer_type and pricing_model.
      - defaults    : pre-filled field values.
      - pipeline_agents / what_happens_next : displayed in the launch step
        to explain what will run after submission.
    """
    return {
        "steps": [
            {"id": 1, "label": "Domain", "icon": "Globe"},
            {"id": 2, "label": "Company Details", "icon": "Building2"},
            {"id": 3, "label": "Product Intel", "icon": "Layers"},
            {"id": 4, "label": "Launch Pipeline", "icon": "Sparkles"},
        ],
        "what_happens_next": [
            {"icon": "Target", "label": "Domain analysis"},
            {"icon": "Users", "label": "Market mapping"},
            {"icon": "Sparkles", "label": "AI profiling"},
        ],
        "pipeline_agents": [
            "Domain Agent",
            "Competitor Agent",
            "Web Agent",
            "Cleaning Agent",
            "Gap Analysis",
            "ICP Agent",
            "Persona Agent",
            "Outreach Agent",
            "Optimization",
        ],
        "select_options": {
            "customer_type": [
                {"value": "B2B", "label": "B2B"},
                {"value": "B2C", "label": "B2C"},
                {"value": "B2B2C", "label": "B2B2C"},
                {"value": "Government", "label": "Government"},
                {"value": "Marketplace", "label": "Marketplace"},
            ],
            "pricing_model": [
                {"value": "freemium", "label": "Freemium"},
                {"value": "subscription", "label": "Subscription"},
                {"value": "usage_based", "label": "Usage Based"},
                {"value": "enterprise", "label": "Enterprise"},
                {"value": "one_time", "label": "One Time"},
                {"value": "other", "label": "Other"},
            ],
        },
        "defaults": {
            "industry": "B2B SaaS",
            "target_geography": "Global",
            "core_problem_solved": "General process inefficiency",
        },
    }


@router.get("/auth-copy", summary="Login/Signup marketing copy")
async def get_auth_copy() -> dict:
    """GET /ui/auth-copy

    Returns the left-panel marketing copy for the login and signup pages
    (title, subtitle, bullet points).  Keeping this server-side avoids
    hardcoding sales copy in the compiled frontend bundle.
    """
    return {
        "login_left": {
            "title": "AI-powered sales intelligence at your fingertips",
            "subtitle": (
                "Automate competitor analysis, generate ICPs, build personas, and craft personalized outreach — "
                "all powered by autonomous AI agents."
            ),
            "bullets": [
                "9 Autonomous AI Agents",
                "Real-time Gap Analysis",
                "Personalized Outreach at Scale",
            ],
        },
        "signup_left": {
            "title": "Start closing deals faster today",
            "subtitle": "Set up your workspace in under 2 minutes. No credit card required. Get instant access to all 9 AI agents.",
            "bullets": [
                "Unlimited competitor analysis",
                "AI-generated ICPs & personas",
                "Multi-channel outreach engine",
                "Real-time analytics dashboard",
            ],
        },
        "app_name": "Sales Agentic AI",
    }


@router.get("/personas", summary="Persona page section configuration")
async def get_personas_config() -> dict:
    """GET /ui/personas

    Returns section definitions for the persona detail page.  Each section
    has a key (matching a field in the BuyerPersona schema), a label, a
    Lucide icon name, and Tailwind colour classes.  The frontend maps over
    this list to render each section card without knowing the field names.
    """
    return {
        "sections": [
            {"key": "goals", "label": "Goals", "icon": "Target", "color": "text-success", "bg": "bg-success/[0.06]"},
            {"key": "pain_points", "label": "Pain Points", "icon": "AlertTriangle", "color": "text-warning", "bg": "bg-warning/[0.06]"},
            {"key": "objections", "label": "Objections", "icon": "MessageSquare", "color": "text-destructive", "bg": "bg-destructive/[0.06]"},
            {"key": "buying_triggers", "label": "Buying Triggers", "icon": "Zap", "color": "text-primary", "bg": "bg-primary/[0.06]"},
        ]
    }

