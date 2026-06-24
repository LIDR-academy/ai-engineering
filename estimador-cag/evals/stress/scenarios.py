"""Deterministic Session 06 multi-turn stress scenarios."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StressTurn:
    turn_index: int
    transcript: str
    fact_to_remember: str


@dataclass(frozen=True)
class StressScenario:
    name: str
    turns: list[StressTurn]


def _turn(index: int, transcript: str, fact: str) -> StressTurn:
    return StressTurn(turn_index=index, transcript=transcript, fact_to_remember=fact)


def _growing_turns() -> list[StressTurn]:
    project = "Project: Nimbus Portal."
    additions = [
        ("The project called Nimbus Portal needs authentication for B2B customers.", "project name: Nimbus Portal"),
        ("Add multi tenant company workspaces with admin invitations.", "scope includes multi tenant workspaces"),
        ("Add audit log for sensitive customer operations.", "scope includes audit log"),
        ("Add CSV export for finance users.", "scope includes CSV export"),
        ("Add reporting dashboard with project level filters.", "scope includes reporting dashboard"),
        ("Add role permissions for owner, manager, and viewer.", "scope includes role permissions"),
        ("Add Slack alerts for failed imports and billing events.", "scope includes Slack alerts"),
        ("Add Stripe billing with invoices and seat limits.", "scope includes Stripe billing"),
        ("Add data import from legacy spreadsheets.", "scope includes data import"),
        ("Add admin panel for support operators.", "scope includes admin panel"),
        ("Add GDPR export and deletion workflow.", "scope includes GDPR export"),
        ("Add SAML SSO for enterprise customers.", "scope includes SAML SSO"),
        ("Add API keys for partner integrations.", "scope includes API keys"),
        ("Add webhook delivery with retry rules.", "scope includes webhook delivery"),
        ("Add background jobs for large exports.", "scope includes background jobs"),
        ("Add usage analytics for product managers.", "scope includes usage analytics"),
        ("Add onboarding checklist for first time teams.", "scope includes onboarding checklist"),
        ("Add billing reconciliation report for accounting.", "scope includes billing reconciliation"),
        ("Add incident notification templates.", "scope includes incident notifications"),
        ("Keep Nimbus Portal as the project name and preserve the full enterprise SaaS scope.", "project name: Nimbus Portal"),
    ]
    return [_turn(i, f"{project} {text}", fact) for i, (text, fact) in enumerate(additions, 1)]


def _pivot_turns() -> list[StressTurn]:
    additions = [
        ("Project: Aurora Field. Build a React web portal for field service scheduling.", "project name: Aurora Field"),
        ("The backend should use FastAPI with PostgreSQL for job assignments.", "stack includes FastAPI"),
        ("Add offline drafts for technicians working without signal.", "scope includes offline drafts"),
        ("Add manager approval for completed work orders.", "scope includes manager approval"),
        ("Pivot the client app from React to Flutter because technicians need native mobile features.", "stack includes Flutter"),
        ("Keep PostgreSQL but expose a mobile friendly API for Flutter.", "stack includes PostgreSQL"),
        ("Add push notifications for urgent dispatch changes.", "scope includes push notifications"),
        ("Add device photo uploads with compression.", "scope includes photo uploads"),
        ("Add location check in for each work order.", "scope includes location check in"),
        ("Add supervisor dashboard on the web for operations.", "scope includes supervisor dashboard"),
        ("Add role permissions for dispatcher and technician.", "scope includes role permissions"),
        ("Add export to the accounting system every Friday.", "scope includes accounting export"),
        ("Add tenant separation for multiple service companies.", "scope includes tenant separation"),
        ("Add alerting when a job is blocked for more than two hours.", "scope includes blocked job alerts"),
        ("Add audit trail for status changes.", "scope includes audit trail"),
        ("Add reporting by technician utilization.", "scope includes utilization reporting"),
        ("Add emergency override for operations leads.", "scope includes emergency override"),
        ("Add document templates for client sign off.", "scope includes sign off templates"),
        ("Add external API for partner dispatch systems.", "scope includes partner API"),
        ("The current committed stack is Flutter plus FastAPI and PostgreSQL.", "stack includes Flutter"),
    ]
    return [_turn(i, text, fact) for i, (text, fact) in enumerate(additions, 1)]


def _contradiction_turns() -> list[StressTurn]:
    additions = [
        ("Project: Boreal Ledger. Build an internal finance approval tool.", "project name: Boreal Ledger"),
        ("The tool needs invoice intake, approval routing, and export to accounting.", "scope includes invoice intake"),
        ("The budget is locked: 30000 EUR for the first release.", "budget locked: 30000 EUR"),
        ("Use Spring Boot, PostgreSQL, and Docker because the backend team knows Java.", "stack includes Spring Boot"),
        ("Add audit log for finance compliance.", "scope includes audit log"),
        ("Add OCR queue for incoming invoice PDFs.", "scope includes OCR queue"),
        ("Add role permissions for requester, approver, and finance admin.", "scope includes finance roles"),
        ("Budget changed to 80000 EUR after compliance expanded the audit scope.", "budget changed to 80000 EUR"),
        ("Deadline changed to twelve weeks because security review is mandatory.", "deadline changed to twelve weeks"),
        ("Add SSO with SAML for internal identity.", "scope includes SAML SSO"),
        ("Add Slack notifications for rejected invoices.", "scope includes Slack notifications"),
        ("Add CSV export for the finance controller.", "scope includes CSV export"),
        ("Add archived invoice search by vendor and month.", "scope includes invoice search"),
        ("Add dashboard for budget owner approvals.", "scope includes approval dashboard"),
        ("Add escalation workflow for overdue approvals.", "scope includes escalation workflow"),
        ("Add immutable event log for audit evidence.", "scope includes immutable event log"),
        ("Add data retention rules for seven years.", "scope includes data retention"),
        ("Add admin panel for finance operations.", "scope includes admin panel"),
        ("Add integration test suite for accounting export.", "scope includes integration tests"),
        ("The latest committed budget is 80000 EUR, not 30000 EUR.", "budget changed to 80000 EUR"),
    ]
    return [_turn(i, text, fact) for i, (text, fact) in enumerate(additions, 1)]


SCENARIOS: dict[str, StressScenario] = {
    "growing": StressScenario(name="growing", turns=_growing_turns()),
    "pivot": StressScenario(name="pivot", turns=_pivot_turns()),
    "contradiction": StressScenario(name="contradiction", turns=_contradiction_turns()),
}


def get_scenarios(names: list[str] | None = None) -> list[StressScenario]:
    if not names:
        return list(SCENARIOS.values())
    missing = [name for name in names if name not in SCENARIOS]
    if missing:
        raise ValueError(f"Unknown stress scenarios: {', '.join(missing)}")
    return [SCENARIOS[name] for name in names]
