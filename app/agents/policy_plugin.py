from dataclasses import dataclass
from app.observability.telemetry import redact_pii


@dataclass
class PolicyEvaluationResult:
    passed: bool
    violations: list[str]
    sanitized_response: str


def evaluate_advisor_response(
    response_text: str,
    proposes_mutation: bool = False,
    has_hitl_approval_request: bool = False,
) -> PolicyEvaluationResult:
    """Self-evaluation guardrail checking sustainability metrics, HITL gates, and redaction."""
    violations: list[str] = []
    lowered = response_text.lower()

    if not any(token in lowered for token in ("usd", "$", "kg co2e", "co2")):
        violations.append("MISSING_COST_OR_CARBON_METRICS")

    if proposes_mutation and not has_hitl_approval_request:
        violations.append("MISSING_HITL_APPROVAL_FOR_MUTATION")

    cleaned = redact_pii(response_text)
    return PolicyEvaluationResult(
        passed=len(violations) == 0,
        violations=violations,
        sanitized_response=cleaned,
    )
