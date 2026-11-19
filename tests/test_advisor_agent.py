import asyncio
from app.agents.advisor_agent import efficiency_analyst_agent, root_agent
from app.agents.session_manager import AdvisorSessionStore
from app.observability.telemetry import log_structured_event, redact_pii
from app.tools.sustainability_tools import (
    request_infrastructure_remediation_approval,
    scan_idle_compute_instances,
)


def test_agent_hierarchy_and_models():
    assert root_agent.name == "sustainable_cloud_advisor"
    assert len(root_agent.sub_agents) == 1
    assert efficiency_analyst_agent.name == "efficiency_analyst"


def test_scan_idle_compute_instances_success_and_validation():
    result = scan_idle_compute_instances(project_id="ctsal200", region="us-central1", min_idle_days=7)
    assert result["project_id"] == "ctsal200"
    assert result["total_potential_monthly_savings_usd"] == 319.0
    assert result["total_potential_monthly_kg_co2e_reduction"] == 47.5

    bad_proj = scan_idle_compute_instances(project_id="   ")
    assert bad_proj["error"] == "INVALID_PROJECT_ID"
    assert "recovery_hint" in bad_proj


def test_hitl_remediation_approval_flow():
    req = request_infrastructure_remediation_approval(
        resource_name="dev-ml-gpu-worker-01",
        proposed_action="Stop idle GPU instance outside business hours",
        estimated_monthly_cost_usd=285.0,
        estimated_monthly_kg_co2e_reduction=42.4,
    )
    assert req["status"] == "PENDING_HUMAN_APPROVAL"
    assert req["approval_id"].startswith("APR-")


def test_pii_redaction_and_intent_outcome_logging():
    scrubbed = redact_pii("Contact alice@company.com or 555-123-4567 from 10.0.0.5")
    assert "alice@company.com" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "[REDACTED_IP]" in scrubbed

    event = log_structured_event(
        event_type="scan_audit",
        intent="Scan ctsal200 for idle VMs",
        outcome="Identified 2 optimization candidates",
    )
    assert event["intent"] == "Scan ctsal200 for idle VMs"
    assert event["outcome"] == "Identified 2 optimization candidates"


def test_session_compaction_and_async_memory():
    async def _run():
        store = AdvisorSessionStore(max_history_turns=3)
        for idx in range(6):
            await store.record_turn_and_consolidate_async(
                session_id="sess-1",
                role="user",
                content=f"Check idle resources turn {idx} for user{idx}@example.com",
                project_id="ctsal200",
            )
        sess = store.get_or_create_session("sess-1")
        assert len(sess["history"]) == 3
        assert len(sess["compacted_summary"]) > 0
        assert all("@example.com" not in n for n in sess["memory_notes"])

    asyncio.run(_run())
