"""Mandile SEO five-part AI employee scaffold. Standard library only; dry-run only."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class Model(Protocol):
    def draft_reply(self, business: str, service: str) -> str: ...


@dataclass(frozen=True)
class DemoModel:
    """Deterministic offline stand-in. Replace via a separately reviewed model adapter."""

    def draft_reply(self, business: str, service: str) -> str:
        safe_business = re.sub(r"[^a-zA-Z0-9 &'-]", "", business)[:48] or "our team"
        safe_service = re.sub(r"[^a-zA-Z0-9 &'-]", "", service)[:40] or "your request"
        return (
            f"Thanks for calling {safe_business}. We missed your call about "
            f"{safe_service}. Would you like a team member to follow up? "
            "Reply YES and we will pass your request to a person."
        )


class Memory:
    """SQLite audit ledger, separated by tenant and event ID. No cross-tenant queries."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(db_path))
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
              tenant_id TEXT NOT NULL,
              event_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              PRIMARY KEY (tenant_id, event_id)
            );
            CREATE TABLE IF NOT EXISTS proposals (
              tenant_id TEXT NOT NULL,
              event_id TEXT NOT NULL,
              phone TEXT NOT NULL,
              message TEXT NOT NULL,
              state TEXT NOT NULL DEFAULT 'pending_approval',
              PRIMARY KEY (tenant_id, event_id),
              FOREIGN KEY (tenant_id, event_id)
                REFERENCES events(tenant_id, event_id)
            );
            """
        )

    def propose(self, tenant_id: str, event_id: str, event_type: str, phone: str, message: str) -> bool:
        with self.db:
            inserted = self.db.execute(
                "INSERT OR IGNORE INTO events VALUES (?, ?, ?)",
                (tenant_id, event_id, event_type),
            ).rowcount
            if inserted:
                self.db.execute(
                    "INSERT INTO proposals (tenant_id,event_id,phone,message) VALUES (?,?,?,?)",
                    (tenant_id, event_id, phone, message),
                )
            return bool(inserted)

    def approve(self, tenant_id: str, event_id: str) -> bool:
        with self.db:
            return bool(self.db.execute(
                "UPDATE proposals SET state='approved_not_sent' "
                "WHERE tenant_id=? AND event_id=? AND state='pending_approval'",
                (tenant_id, event_id),
            ).rowcount)

    def list_proposals(self, tenant_id: str) -> list[dict[str, str]]:
        rows = self.db.execute(
            "SELECT event_id, phone, message, state FROM proposals WHERE tenant_id=? ORDER BY event_id",
            (tenant_id,),
        ).fetchall()
        return [dict(zip(("event_id", "phone", "message", "state"), r)) for r in rows]


class DryRunConnector:
    """Proposes messages only; no SMS/email/CRM/network API access."""

    def __init__(self, memory: Memory) -> None:
        self.memory = memory

    def queue(self, tenant_id: str, event_id: str, phone: str, message: str) -> bool:
        return self.memory.propose(tenant_id, event_id, "missed_call", phone, message)


class AgentHarness:
    """Validates input and gates actions before connectors are invoked."""

    def __init__(self, memory: Memory, model: Model | None = None) -> None:
        self.memory = memory
        self.model = model or DemoModel()
        self.connector = DryRunConnector(memory)

    def handle_missed_call(self, tenant_id: str, event: dict[str, str]) -> dict[str, str]:
        if not tenant_id or len(tenant_id) > 80 or not re.fullmatch(r"[a-zA-Z0-9_-]+", tenant_id):
            raise ValueError("Invalid tenant ID")
        event_id = str(event.get("event_id", ""))
        phone = str(event.get("phone", ""))
        if not event_id or len(event_id) > 120 or not re.fullmatch(r"[a-zA-Z0-9_-]+", event_id):
            raise ValueError("Invalid event ID")
        if not re.fullmatch(r"\+?[0-9][0-9() .-]{6,20}", phone):
            raise ValueError("Invalid callback number")
        business = str(event.get("business", ""))
        service = str(event.get("service", ""))
        message = self.model.draft_reply(business, service)
        created = self.connector.queue(tenant_id, event_id, phone, message)
        return {
            "tenant_id": tenant_id,
            "event_id": event_id,
            "result": "pending_approval" if created else "duplicate_ignored",
            "delivery": "never_sent",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mandile agent dry-run scaffold")
    parser.add_argument("command", choices=["demo", "list", "approve"])
    parser.add_argument("--db", default="mandile-agent.sqlite3")
    parser.add_argument("--tenant", default="demo_contractor")
    parser.add_argument("--event-id", default="missedcall_001")
    args = parser.parse_args()
    memory = Memory(args.db)
    if args.command == "demo":
        result = AgentHarness(memory).handle_missed_call(
            args.tenant,
            {"event_id": args.event_id, "phone": "+16235550100", "business": "Demo Plumbing", "service": "plumbing repair"},
        )
    elif args.command == "approve":
        result = {"approved": memory.approve(args.tenant, args.event_id), "delivery": "never_sent"}
    else:
        result = memory.list_proposals(args.tenant)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
