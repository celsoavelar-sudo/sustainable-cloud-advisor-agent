import json
import logging
import re
import time
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("sustainable_cloud_advisor")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

try:
    from opentelemetry import trace  # type: ignore

    _tracer = trace.get_tracer("sustainable-cloud-advisor-agent")
except Exception:  # pragma: no cover
    _tracer = None

_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[REDACTED_PHONE]"),
    (re.compile(r"\b(?:AIza[0-9A-Za-z\-_]{35}|gho_[0-9A-Za-z]{36}|sk-[0-9A-Za-z]{20,})\b"), "[REDACTED_SECRET]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[REDACTED_IP]"),
]


def redact_pii(value: Any) -> Any:
    """Recursively scrubs PII and secrets from strings, dicts, and lists before logging."""
    if isinstance(value, str):
        redacted = value
        for pattern, replacement in _PII_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted
    if isinstance(value, dict):
        return {str(k): redact_pii(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_pii(item) for item in value]
    return value


def log_structured_event(
    event_type: str,
    intent: str,
    outcome: str,
    status: str = "ok",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emits a structured JSON log capturing both intended action and actual outcome."""
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event_type": event_type,
        "status": status,
        "intent": redact_pii(intent),
        "outcome": redact_pii(outcome),
        "metadata": redact_pii(metadata or {}),
    }
    logger.info(json.dumps(payload, ensure_ascii=True))
    return payload


@contextmanager
def trace_span(span_name: str, attributes: dict[str, Any] | None = None):
    """Creates an OpenTelemetry span when available and records timing/status."""
    start = time.perf_counter()
    safe_attrs = redact_pii(attributes or {})
    if _tracer is not None:
        with _tracer.start_as_current_span(span_name) as span:
            for key, val in safe_attrs.items():
                span.set_attribute(key, str(val))
            try:
                yield span
            except Exception as exc:
                span.record_exception(exc)
                raise
            finally:
                span.set_attribute("duration_ms", round((time.perf_counter() - start) * 1000, 2))
    else:
        yield None
