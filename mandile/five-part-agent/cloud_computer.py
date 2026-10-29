"""Mandile Orgo cloud computer adapter. Dry-run by default. No agent deployed."""
from __future__ import annotations
import argparse
import json
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE = "https://www.orgo.ai/api"
IDENT = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
COMPUTER_ID = re.compile(r"^[a-fA-F0-9-]{36}$")

@dataclass(frozen=True)
class ComputerSpec:
    tenant_id: str
    agent_name: str
    workspace_id: str
    ram_gb: int = 8
    cpu: int = 2
    auto_stop_minutes: int | None = 30
    template_ref: str | None = None

    def __post_init__(self) -> None:
        if not IDENT.fullmatch(self.tenant_id) or not IDENT.fullmatch(self.agent_name):
            raise ValueError("Tenant and agent must be lowercase identifiers")
        uuid.UUID(self.workspace_id)
        if self.ram_gb not in (4, 8, 16, 32) or self.cpu not in (1, 2, 4, 6):
            raise ValueError("Invalid RAM or CPU size")
        if self.auto_stop_minutes is not None and not 0 <= self.auto_stop_minutes <= 1440:
            raise ValueError("auto_stop_minutes must be 0-1440")
        if self.template_ref and not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+@[A-Za-z0-9_.-]+", self.template_ref):
            raise ValueError("template_ref must be namespace/name@version")
        if len(self.name) > 80:
            raise ValueError("Computer name too long")

    @property
    def name(self) -> str:
        return f"mandile-{self.tenant_id}-{self.agent_name}"

    def create_payload(self) -> dict[str, Any]:
        data = {"workspace_id": self.workspace_id, "name": self.name,
                "os": "linux", "ram": self.ram_gb, "cpu": self.cpu, "billing_mode": "plan"}
        if self.auto_stop_minutes is not None:
            data["auto_stop_minutes"] = self.auto_stop_minutes
        if self.template_ref:
            data["template_ref"] = self.template_ref
        return data

    def idempotency_key(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, "mandile-cloud-computer:" + self.workspace_id + "/" + self.name))

def safe_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Do not log Orgo's VNC passwords or private connection details."""
    allowed = ("id", "name", "workspace_id", "project_id", "status",
               "os", "ram", "cpu", "connection_url")
    return {key: data[key] for key in allowed if key in data}

class OrgoCloud:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Set ORGO_API_KEY in your environment")
        self.api_key = api_key

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None,
                 idempotency_key: str | None = None) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Authorization": "Bearer " + self.api_key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = Request(API_BASE + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read(2_000_000) or b"{}")
                if not isinstance(data, dict):
                    raise RuntimeError("Orgo returned an unexpected response")
                return data
        except HTTPError as exc:
            raise RuntimeError(f"Orgo API returned HTTP {exc.code} for {method} {path}") from None
        except URLError:
            raise RuntimeError(f"Orgo connectivity error for {method} {path}") from None

    def create(self, spec: ComputerSpec) -> dict[str, Any]:
        result = self._request("POST", "/computers", spec.create_payload(), spec.idempotency_key())
        if not result.get("id"):
            raise RuntimeError("Orgo response had no computer ID")
        return safe_summary(result)

    def get(self, computer_id: str) -> dict[str, Any]:
        self._validate_id(computer_id)
        return safe_summary(self._request("GET", f"/computers/{computer_id}"))

    def stop(self, computer_id: str) -> dict[str, Any]:
        self._validate_id(computer_id)
        result = self._request("POST", f"/computers/{computer_id}/stop", {"async": False})
        return {"computer_id": computer_id, "stop_response":
                {k: result[k] for k in ("success", "status") if k in result}}

    @staticmethod
    def _validate_id(value: str) -> None:
        if not COMPUTER_ID.fullmatch(value):
            raise ValueError("computer_id must be a UUID")

def main() -> None:
    p = argparse.ArgumentParser(description="Mandile Orgo cloud computers")
    p.add_argument("action", choices=("plan", "create", "get", "stop"))
    p.add_argument("--tenant", default="demo_client")
    p.add_argument("--agent", default="lead_recovery")
    p.add_argument("--workspace-id", default=os.getenv("ORGO_WORKSPACE_ID", ""))
    p.add_argument("--computer-id", default="")
    p.add_argument("--ram", type=int, default=8)
    p.add_argument("--cpu", type=int, default=2)
    p.add_argument("--auto-stop", type=int, default=30)
    p.add_argument("--template-ref")
    p.add_argument("--apply", action="store_true", help="Actually create/stop a cloud computer")
    args = p.parse_args()
    if args.action in ("plan", "create"):
        if not args.workspace_id:
            p.error("--workspace-id or ORGO_WORKSPACE_ID required")
        spec = ComputerSpec(args.tenant, args.agent, args.workspace_id,
                            args.ram, args.cpu, args.auto_stop, args.template_ref)
        if args.action == "plan" or not args.apply:
            result = {"mode": "DRY_RUN", "action": "create", "payload": spec.create_payload(),
                      "requires": "--apply and ORGO_API_KEY"}
        else:
            result = {"mode": "LIVE", "computer": OrgoCloud(os.getenv("ORGO_API_KEY", "")).create(spec)}
    else:
        if not args.computer_id:
            p.error("--computer-id required")
        if args.action == "stop" and not args.apply:
            result = {"mode": "DRY_RUN", "action": "stop", "computer_id": args.computer_id}
        else:
            provider = OrgoCloud(os.getenv("ORGO_API_KEY", ""))
            result = provider.get(args.computer_id) if args.action == "get" else provider.stop(args.computer_id)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
