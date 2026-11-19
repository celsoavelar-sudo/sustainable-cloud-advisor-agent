import os
from google.adk.agents import Agent
from app.tools.sustainability_tools import (
    request_infrastructure_remediation_approval,
    scan_idle_compute_instances,
)

FAST_MODEL = os.getenv("ADK_FAST_MODEL", "gemini-2.5-flash")
PLANNING_MODEL = os.getenv("ADK_PLANNING_MODEL", "gemini-2.5-pro")

SYSTEM_CONSTITUTION = """
You are the Sustainable Cloud Advisor Agent.
Mission: Help engineering teams reduce cloud waste, lower operating costs, and cut carbon emissions
across Google Cloud workloads without risking production reliability.

Operating Rules:
1. Always ground resource findings in tool outputs rather than inventing metrics.
2. Quantify both estimated monthly cost savings (USD) and estimated carbon reduction (kg CO2e).
3. Never execute or claim completion of destructive or state-changing resource actions without first
   calling `request_infrastructure_remediation_approval` and obtaining explicit human confirmation.
4. If a tool returns an error or recovery_hint, follow the recovery instructions cleanly.
5. Never expose secrets, credentials, or raw PII in responses.
"""

efficiency_analyst_agent = Agent(
    name="efficiency_analyst",
    model=FAST_MODEL,
    description="Scans cloud compute and storage utilization and quantifies cost and carbon savings.",
    instruction=(
        "You are the Efficiency Analyst sub-agent. Use `scan_idle_compute_instances` to inspect "
        "workloads and summarize idle/overprovisioned resources, monthly USD savings, and kg CO2e reductions."
    ),
    tools=[scan_idle_compute_instances],
)

root_agent = Agent(
    name="sustainable_cloud_advisor",
    model=PLANNING_MODEL,
    description="Coordinates sustainability audits, prioritization, and human-in-the-loop remediation approvals.",
    instruction=SYSTEM_CONSTITUTION,
    sub_agents=[efficiency_analyst_agent],
    tools=[
        scan_idle_compute_instances,
        request_infrastructure_remediation_approval,
    ],
)
