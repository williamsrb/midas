"""Wire-contract mirror of morpheus's assignment lifecycle (spec §4.4, S4b).

Hand-written to match `morpheus/packages/fleet-contract/src/assignments.ts` field-for-field -
same caveat as `fleet/manifest.py`: no codegen pipeline exists, so this must be kept in sync by
hand. Unlike the manifest/patch contract, nothing here is signed or hashed, so there is no
byte-exact canonicalization to get right - these are just the documented JSON shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DocumentRef:
    path: str
    sha256: str
    size: int


@dataclass
class WorkspaceSpec:
    kind: str  # "git" | "none"
    reuse: bool = True
    repo_url: str | None = None
    branch: str | None = None

    @classmethod
    def from_json(cls, data: dict) -> "WorkspaceSpec":
        return cls(kind=str(data["kind"]), reuse=bool(data.get("reuse", True)), repo_url=data.get("repoUrl"), branch=data.get("branch"))


@dataclass
class AssignmentLimits:
    max_usd: float | None = None
    max_minutes: float | None = None
    permission_ceiling: str | None = None  # "readonly" | "edits" | "full"

    @classmethod
    def from_json(cls, data: dict) -> "AssignmentLimits":
        return cls(max_usd=data.get("maxUsd"), max_minutes=data.get("maxMinutes"), permission_ceiling=data.get("permissionCeiling"))


@dataclass
class RoutingHint:
    subscription: str
    model: str | None = None


@dataclass
class Assignment:
    assignment_id: str
    idempotency_key: str
    attempt: int
    max_attempts: int
    lease_until: str
    priority: int
    kernel_version: str
    harness_version: str
    playbook: dict
    inputs: dict  # {"vars": dict, "documents": list[DocumentRef]}
    workspace: WorkspaceSpec
    limits: AssignmentLimits
    routing: dict[str, RoutingHint] = field(default_factory=dict)
    run_id: str | None = None

    @classmethod
    def from_json(cls, data: dict) -> "Assignment":
        inputs = data.get("inputs", {})
        return cls(
            assignment_id=str(data["assignmentId"]),
            idempotency_key=str(data["idempotencyKey"]),
            run_id=data.get("runId"),
            attempt=int(data["attempt"]),
            max_attempts=int(data["maxAttempts"]),
            lease_until=str(data["leaseUntil"]),
            priority=int(data["priority"]),
            kernel_version=str(data["kernelVersion"]),
            harness_version=str(data["harnessVersion"]),
            playbook=dict(data.get("playbook", {})),
            inputs={
                "vars": dict(inputs.get("vars", {})),
                "documents": [DocumentRef(**d) for d in inputs.get("documents", [])],
            },
            workspace=WorkspaceSpec.from_json(data["workspace"]),
            limits=AssignmentLimits.from_json(data.get("limits", {})),
            routing={k: RoutingHint(**v) for k, v in data.get("routing", {}).items()},
        )


@dataclass
class ClaimResponse:
    assignments: list[Assignment]

    @classmethod
    def from_json(cls, data: dict) -> "ClaimResponse":
        return cls(assignments=[Assignment.from_json(a) for a in data.get("assignments", [])])


@dataclass
class ArtifactRef:
    path: str
    sha256: str
    size: int


@dataclass
class Gate:
    node_id: str
    prompt: str


@dataclass
class CompleteRequest:
    outcome: str  # "succeeded" | "failed" | "gate"
    spend_usd: float
    baton_digest: str
    artifacts: list[ArtifactRef] = field(default_factory=list)
    gate: Gate | None = None

    def to_json(self) -> dict:
        body: dict = {
            "outcome": self.outcome,
            "spendUsd": self.spend_usd,
            "batonDigest": self.baton_digest,
            "artifacts": [{"path": a.path, "sha256": a.sha256, "size": a.size} for a in self.artifacts],
        }
        if self.gate is not None:
            body["gate"] = {"nodeId": self.gate.node_id, "prompt": self.gate.prompt}
        return body


@dataclass
class NackRequest:
    reason: str
    retryable: bool
    detail: str | None = None

    def to_json(self) -> dict:
        body: dict = {"reason": self.reason, "retryable": self.retryable}
        if self.detail is not None:
            body["detail"] = self.detail
        return body


@dataclass
class AssignmentEvent:
    seq: int
    at: str
    type: str
    node_id: str | None = None
    data: object = None

    def to_json(self) -> dict:
        body: dict = {"seq": self.seq, "at": self.at, "type": self.type}
        if self.node_id is not None:
            body["nodeId"] = self.node_id
        if self.data is not None:
            body["data"] = self.data
        return body


@dataclass
class AssignmentUsage:
    at: str
    step_id: str
    subscription: str
    estimated_usd: float | None
    cost_source: str | None = None  # "reported" | "estimated"

    def to_json(self) -> dict:
        body: dict = {"at": self.at, "stepId": self.step_id, "subscription": self.subscription, "estimatedUsd": self.estimated_usd}
        if self.cost_source is not None:
            body["costSource"] = self.cost_source
        return body
