"""Drata MCP Server - SOC2 Type II Compliance Task Management."""

import os
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .client import DrataClient

load_dotenv()

# Initialize MCP server
mcp = FastMCP(
    "Drata Compliance",
    instructions="""You are a SOC2 Type II compliance assistant connected to Drata.

IMPORTANT TOOL SELECTION:
- For "controls pas bon" / "bad controls" / "failing controls" → use list_controls_with_issues
- For "tests en échec" / "failing tests" → use list_failing_monitors
- For "tests d'un control" → use get_monitors_for_control
- For dashboard overview → use get_compliance_summary

Controls have derived statuses: PASSING, NEEDS_EVIDENCE, NOT_READY, NO_OWNER, ARCHIVED.
Monitors (tests) have statuses: PASSED, FAILED, NOT_TESTED.

DATA FRESHNESS: Drata's public API cannot trigger a monitor rerun or an
integration sync (that only exists in the web UI as "Test now" on a test's
Monitoring page, and via Autopilot's automatic daily runs). Monitor results
may therefore lag infrastructure changes by up to ~24h. Always check a
monitor's lastCheck timestamp before treating a FAILED result as current;
if resources were remediated after lastCheck, tell the user to use "Test
now" in the Drata UI or wait for the next Autopilot run.

Always prioritize FAILED or non-compliant items first.""",
)

# Global client instance
_client: DrataClient | None = None



def get_client() -> DrataClient:
    """Get or create Drata client."""
    global _client
    if _client is None:
        api_key = os.getenv("DRATA_API_KEY")
        if not api_key:
            raise ValueError("DRATA_API_KEY environment variable is required")
        region = os.getenv("DRATA_REGION", "us")
        _client = DrataClient(api_key, region)
    return _client


# ==================== CONTROLS TOOLS ====================


def _get_control_status(c: dict) -> str:
    """Derive control status from flags."""
    if c.get("archivedAt"):
        return "ARCHIVED"
    if not c.get("isReady"):
        return "NOT_READY"
    if not c.get("hasOwner"):
        return "NO_OWNER"
    if c.get("isMonitored") and c.get("hasEvidence"):
        return "PASSING"
    if not c.get("hasEvidence"):
        return "NEEDS_EVIDENCE"
    return "READY"


@mcp.tool()
async def list_controls(
    search: str | None = None,
    only_issues: bool = False,
) -> dict[str, Any]:
    """List ALL compliance controls with optional search.

    Args:
        search: Search term for control name/description
        only_issues: If True, only show controls with problems (not ready, no owner, no evidence)

    Returns:
        List of controls with their status and details
    """
    client = get_client()
    result = await client.list_all_controls(search=search)

    controls = result.get("data", [])

    # Add derived status
    enriched = []
    for c in controls:
        status = _get_control_status(c)
        if only_issues and status in ("PASSING", "READY", "ARCHIVED"):
            continue
        enriched.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "code": c.get("code"),
            "status": status,
            "isMonitored": c.get("isMonitored"),
            "hasEvidence": c.get("hasEvidence"),
            "hasOwner": c.get("hasOwner"),
            "frameworks": c.get("frameworkTags", []),
        })

    # Summary
    not_ready = sum(1 for c in enriched if c["status"] == "NOT_READY")
    no_owner = sum(1 for c in enriched if c["status"] == "NO_OWNER")
    needs_evidence = sum(1 for c in enriched if c["status"] == "NEEDS_EVIDENCE")

    return {
        "total": result.get("total", len(controls)),
        "showing": len(enriched),
        "summary": {
            "not_ready": not_ready,
            "no_owner": no_owner,
            "needs_evidence": needs_evidence,
        },
        "controls": enriched,
    }


@mcp.tool()
async def get_control_details(control_code: str) -> dict[str, Any]:
    """Get detailed information about a specific control.

    Args:
        control_code: The control code (e.g., "DCF-71", "DCF-12")

    Returns:
        Full control details including linked monitors
    """
    client = get_client()

    # Search for the control by code
    result = await client.list_controls(limit=50, search=control_code)
    controls = result.get("data", [])

    # Find exact match
    control = None
    for c in controls:
        if c.get("code") == control_code:
            control = c
            break

    if not control:
        return {"error": f"Control {control_code} not found"}

    # Get linked monitors
    monitors_result = await client.list_monitors(limit=50)
    linked_monitors = []
    for m in monitors_result.get("data", []):
        control_codes = [c.get("code") for c in m.get("controls", [])]
        if control_code in control_codes:
            linked_monitors.append({
                "id": m.get("id"),
                "name": m.get("name"),
                "status": m.get("checkResultStatus"),
                "priority": m.get("priority"),
            })

    return {
        "id": control.get("id"),
        "name": control.get("name"),
        "code": control.get("code"),
        "status": _get_control_status(control),
        "description": control.get("description"),
        "isMonitored": control.get("isMonitored"),
        "hasEvidence": control.get("hasEvidence"),
        "hasOwner": control.get("hasOwner"),
        "isReady": control.get("isReady"),
        "frameworks": control.get("frameworkTags", []),
        "linked_monitors": linked_monitors,
    }


@mcp.tool()
async def list_controls_with_issues() -> dict[str, Any]:
    """Get controls that are NOT OK / have problems / need attention.

    Use this tool when user asks for:
    - "controls pas bon" / "bad controls" / "failing controls"
    - "controls with issues" / "problematic controls"
    - "controls that need work" / "controls à corriger"

    Returns controls with status: NOT_READY, NO_OWNER, or NEEDS_EVIDENCE.

    Returns:
        Controls with compliance issues and their status
    """
    return await list_controls(only_issues=True)


@mcp.tool()
async def get_monitors_for_control(control_code: str) -> dict[str, Any]:
    """Get all monitors (tests) that affect a specific control.

    Args:
        control_code: The control code (e.g., "DCF-71")

    Returns:
        List of monitors linked to this control
    """
    client = get_client()
    result = await client.list_all_monitors()

    monitors = result.get("data", [])
    linked = []

    for m in monitors:
        control_codes = [c.get("code") for c in m.get("controls", [])]
        if control_code in control_codes:
            linked.append({
                "id": m.get("id"),
                "name": m.get("name"),
                "status": m.get("checkResultStatus"),
                "priority": m.get("priority"),
                "lastCheck": m.get("lastCheck"),
            })

    return {
        "control_code": control_code,
        "total_monitors": len(linked),
        "monitors": linked,
    }


# ==================== MONITORS (Automated Tests) TOOLS ====================


@mcp.tool()
async def list_monitors(
    status: str | None = None,
) -> dict[str, Any]:
    """List ALL automated monitoring tests.

    Args:
        status: Filter - PASSED, FAILED, NOT_TESTED

    Returns:
        List of monitoring tests with status summary
    """
    client = get_client()
    result = await client.list_all_monitors(check_result_status=status)

    monitors = result.get("data", [])

    # Count by status
    passed = sum(1 for m in monitors if m.get("checkResultStatus") == "PASSED")
    failed = sum(1 for m in monitors if m.get("checkResultStatus") == "FAILED")
    not_tested = sum(1 for m in monitors if m.get("checkResultStatus") == "NOT_TESTED")

    return {
        "total": result.get("total", len(monitors)),
        "summary": {
            "passed": passed,
            "failed": failed,
            "not_tested": not_tested,
        },
        "monitors": [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "status": m.get("checkResultStatus"),
                "priority": m.get("priority"),
                "lastCheck": m.get("lastCheck"),
                "checkStatus": m.get("checkStatus"),
            }
            for m in monitors
        ],
    }


@mcp.tool()
async def list_failing_monitors() -> dict[str, Any]:
    """Get all FAILED automated monitoring tests - critical for SOC2.

    Returns:
        List of failing tests that need remediation
    """
    client = get_client()
    result = await client.list_all_monitors()

    # Filter to FAILED only
    monitors = result.get("data", [])
    failed = [m for m in monitors if m.get("checkResultStatus") == "FAILED"]

    return {
        "total_failed": len(failed),
        "message": f"🔴 {len(failed)} tests failing" if failed else "🟢 All tests passing",
        "failing_monitors": [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "priority": m.get("priority"),
                "lastCheck": m.get("lastCheck"),
                "description": m.get("description", "")[:200],
                "controls": [c.get("code") for c in m.get("controls", [])],
            }
            for m in failed
        ],
    }


@mcp.tool()
async def get_monitor_details(monitor_id: int) -> dict[str, Any]:
    """Get detailed information about a specific monitor/test,
    including the resources currently failing it.

    Args:
        monitor_id: The monitor's testId (shown in Drata URLs, e.g.
            /monitoring/details/221). A monitor list `id` is also accepted
            and resolved to its testId automatically.

    Returns:
        Full monitor details including failure reasons, remediation,
        and the list of failing resources
    """
    client = get_client()
    workspace_id = await client.get_workspace_id()

    try:
        monitor = await client.get_monitor(workspace_id, monitor_id)
    except Exception:
        # Caller may have passed the monitor list `id` instead of `testId`;
        # resolve it via the list endpoint and retry.
        listing = await client.list_all_monitors()
        match = next(
            (m for m in listing.get("data", []) if m.get("id") == monitor_id),
            None,
        )
        if not match or not match.get("testId"):
            raise ValueError(f"Monitor not found: {monitor_id}")
        monitor = await client.get_monitor(workspace_id, int(match["testId"]))

    test_id = int(monitor.get("testId") or monitor_id)

    instances = monitor.get("monitorInstances") or []
    first_instance = instances[0] if isinstance(instances, list) and instances else {}

    details = {
        "id": monitor.get("id"),
        "testId": test_id,
        "name": monitor.get("name"),
        "description": monitor.get("description"),
        "status": monitor.get("checkResultStatus"),
        "priority": monitor.get("priority"),
        "checkStatus": monitor.get("checkStatus"),
        "lastCheck": monitor.get("lastCheck"),
        "controls": [{"id": c.get("id"), "code": c.get("code")} for c in (monitor.get("controls") or []) if isinstance(c, dict)],
        "failedTestDescription": first_instance.get("failedTestDescription"),
        "remedyDescription": first_instance.get("remedyDescription"),
        "evidenceCollectionDescription": first_instance.get("evidenceCollectionDescription"),
    }

    if monitor.get("checkResultStatus") == "FAILED":
        failures = await client.list_monitor_failures(workspace_id, test_id)
        entries = failures.get("data") or []
        details["failingResources"] = [
            _format_failing_resource(f) for f in entries
        ]
        details["totalFailingResources"] = failures.get("total", len(entries))
        details["freshnessWarning"] = (
            f"Failing resources reflect the last test run at {details['lastCheck']}. "
            "If remediation happened after that, rerun via 'Test now' in the "
            "Drata UI (public API cannot trigger reruns) or wait for the next "
            "daily Autopilot run."
        )

    return details


def _format_failing_resource(f: dict) -> dict[str, Any]:
    """Normalize a v2 /failures entry.

    Drata reuses one finding DTO across wildly different monitor categories,
    and which keys are populated depends on the connection type. Cloud-account
    monitors populate name/resourceArn/region; codebase (IaC-scanning) monitors
    populate resourceName/resourceType/property/repository instead and leave
    every cloud field as an empty string.

    Mapping only the cloud shape made codebase findings render as all-null,
    which hid the actual failures. So map both shapes, treat "" as absent, and
    pass through anything still unrecognized under `extra` rather than dropping
    it -- an unmapped-but-visible field beats a silently empty result.
    """

    def val(*keys: str) -> Any:
        for k in keys:
            v = f.get(k)
            if v not in (None, "", [], {}):
                return v
        return None

    display = val("displayName") or ""
    # displayName is often "resource-id / region / account-id"
    parts = [p.strip() for p in display.split("/")] if display else []
    region = parts[1] if len(parts) == 3 else None

    formatted = {
        "name": val("name", "resourceName", "entityName", "targetName") or display or None,
        "displayName": display or None,
        "resource": val("resource", "resourceType"),
        "resourceArn": val("resourceArn"),
        "accountId": val("accountId") or (parts[2] if len(parts) == 3 else None),
        "region": val("region"),
        "cause": val("cause", "vulnerabilityTitle", "issueTitle"),
        # Codebase-monitor fields: which Terraform property is missing, and where.
        "property": val("property"),
        "repository": val("repository"),
        "severity": val("severity"),
        "findingId": val("findingId", "id"),
    }
    if region and not formatted["region"]:
        formatted["region"] = region

    mapped_keys = {
        "displayName", "name", "resourceName", "entityName", "targetName",
        "resource", "resourceType", "resourceArn", "accountId", "region",
        "cause", "vulnerabilityTitle", "issueTitle", "property", "repository",
        "severity", "findingId", "id",
    }
    extra = {
        k: v for k, v in f.items()
        if k not in mapped_keys and v not in (None, "", [], {})
    }
    if extra:
        formatted["extra"] = extra

    return formatted


@mcp.tool()
async def get_control_compliance(control_code: str) -> dict[str, Any]:
    """Full compliance picture for one control: control -> monitors ->
    failing resources -> owner status, in a single call.

    Args:
        control_code: The control code, e.g. "DCF-406"

    Returns:
        Control summary, every mapped monitor with status, and for each
        FAILED monitor the concrete failing resources (name, ARN, account,
        region, failing rule) plus last-run timestamps
    """
    client = get_client()
    controls = await client.list_all_controls(search=control_code)
    control = next(
        (c for c in controls.get("data", []) if c.get("code") == control_code),
        None,
    )
    if not control:
        raise ValueError(f"Control not found: {control_code}")

    workspace_id = await client.get_workspace_id()
    monitors = await client.list_all_monitors(control_id=control.get("id"))

    monitor_summaries = []
    for m in monitors.get("data", []):
        summary: dict[str, Any] = {
            "id": m.get("id"),
            "testId": m.get("testId"),
            "name": m.get("name"),
            "status": m.get("checkResultStatus"),
            "lastCheck": m.get("lastCheck"),
        }
        if m.get("checkResultStatus") == "FAILED" and m.get("testId"):
            failures = await client.list_monitor_failures(
                workspace_id, int(m["testId"])
            )
            summary["failingResources"] = [
                _format_failing_resource(f) for f in failures.get("data", [])
            ]
            summary["totalFailingResources"] = failures.get("total")
        monitor_summaries.append(summary)

    failed = [m for m in monitor_summaries if m["status"] == "FAILED"]
    return {
        "control": {
            "id": control.get("id"),
            "code": control.get("code"),
            "name": control.get("name"),
            "status": _get_control_status(control),
            "hasOwner": bool(control.get("users")),
            "hasEvidence": control.get("hasEvidence"),
            "isMonitored": control.get("isMonitored"),
        },
        "totalMonitors": len(monitor_summaries),
        "failedMonitors": len(failed),
        "monitors": monitor_summaries,
        "note": (
            "Monitor results update on Drata's daily Autopilot schedule; "
            "compare lastCheck against your remediation time."
        ),
    }


@mcp.tool()
async def add_control_note(control_code: str, comment: str) -> dict[str, Any]:
    """Attach a remediation/status note to a control (visible in Drata UI).

    Use after engineering fixes are deployed to record what was done,
    e.g. "Deleted 14 unused default VPCs (RM-5400); awaiting next test run."

    Args:
        control_code: The control code, e.g. "DCF-406"
        comment: Note text, max 191 characters

    Returns:
        The created note
    """
    if len(comment) > 191:
        raise ValueError("Drata control notes are limited to 191 characters")
    client = get_client()
    controls = await client.list_all_controls(search=control_code)
    control = next(
        (c for c in controls.get("data", []) if c.get("code") == control_code),
        None,
    )
    if not control:
        raise ValueError(f"Control not found: {control_code}")
    workspace_id = await client.get_workspace_id()
    note = await client.create_control_note(workspace_id, control["id"], comment)
    return {
        "created": True,
        "noteId": note.get("id"),
        "control": control_code,
        "comment": note.get("comment"),
        "createdAt": note.get("createdAt"),
    }


async def _find_control(client: DrataClient, control_code: str) -> dict[str, Any]:
    """Resolve a control by its DCF code."""
    controls = await client.list_all_controls(search=control_code)
    control = next(
        (c for c in controls.get("data", []) if c.get("code") == control_code),
        None,
    )
    if not control:
        raise ValueError(f"Control not found: {control_code}")
    return control


@mcp.tool()
async def assign_control_owner(control_code: str, owner_email: str) -> dict[str, Any]:
    """Assign an owner to a control by email address.

    Args:
        control_code: The control code, e.g. "DCF-406"
        owner_email: Email of the Drata user to assign as owner

    Returns:
        Confirmation with the control's current owners
    """
    client = get_client()
    control = await _find_control(client, control_code)
    user = await client.find_user_by_email(owner_email)
    workspace_id = await client.get_workspace_id()

    await client.add_control_owner(workspace_id, control["id"], user["id"])
    owners = await client.list_control_owners(workspace_id, control["id"])
    return {
        "assigned": True,
        "control": control_code,
        "owner": {"id": user["id"], "email": user.get("email")},
        "currentOwners": [
            {"id": o.get("id"), "email": o.get("email"),
             "name": f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()}
            for o in owners.get("data", [])
        ],
    }


@mcp.tool()
async def add_evidence(
    name: str,
    control_codes: list[str] | None = None,
    description: str | None = None,
    url: str | None = None,
    ticket_url: str | None = None,
    owner_email: str | None = None,
    renewal_schedule_type: str = "ONE_YEAR",
    filed_at: str | None = None,
) -> dict[str, Any]:
    """Create an Evidence Library item, optionally with a URL artifact and
    linked controls.

    Args:
        name: Evidence name (max 191 chars)
        control_codes: Control codes to link, e.g. ["DCF-406"]
        description: What this evidence demonstrates
        url: Artifact source URL (e.g. link to runbook, dashboard, PR)
        ticket_url: Artifact source ticket URL (alternative to url)
        owner_email: Evidence owner email — required if url/ticket_url given
        renewal_schedule_type: ONE_YEAR (default), SIX_MONTHS, THREE_MONTHS,
            ONE_MONTH, or CUSTOM — used only when an artifact source is given
        filed_at: ISO date the artifact was filed (defaults to today when an
            artifact source is given)

    Returns:
        The created evidence item
    """
    client = get_client()
    workspace_id = await client.get_workspace_id()

    payload: dict[str, Any] = {"name": name}
    if description:
        payload["description"] = description

    if control_codes:
        control_ids = []
        for code in control_codes:
            control = await _find_control(client, code)
            control_ids.append(control["id"])
        payload["controlIds"] = control_ids

    if url or ticket_url:
        if not owner_email:
            raise ValueError(
                "owner_email is required when providing a url/ticket_url artifact"
            )
        from datetime import date

        user = await client.find_user_by_email(owner_email)
        payload["ownerId"] = user["id"]
        payload["renewalScheduleType"] = renewal_schedule_type
        payload["filedAt"] = filed_at or date.today().isoformat()
        if url:
            payload["url"] = url
        else:
            payload["ticketUrl"] = ticket_url

    evidence = await client.create_evidence(workspace_id, payload)
    return {
        "created": True,
        "evidenceId": evidence.get("id"),
        "name": evidence.get("name"),
        "linkedControls": control_codes or [],
    }


@mcp.tool()
async def link_evidence_to_controls(
    evidence_id: int,
    control_codes: list[str],
) -> dict[str, Any]:
    """Link an existing Evidence Library item to controls.

    Args:
        evidence_id: The Evidence Library item ID
        control_codes: Control codes to link, e.g. ["DCF-406", "DCF-77"]

    Returns:
        Confirmation of the update
    """
    client = get_client()
    workspace_id = await client.get_workspace_id()
    control_ids = []
    for code in control_codes:
        control = await _find_control(client, code)
        control_ids.append(control["id"])
    await client.update_evidence(
        workspace_id, evidence_id, {"controlIds": control_ids}
    )
    return {"updated": True, "evidenceId": evidence_id, "linkedControls": control_codes}


@mcp.tool()
async def get_connections_status() -> dict[str, Any]:
    """List integration connections with state and connection timestamps.

    Useful for judging data freshness (e.g. is the AWS connection healthy).
    Note: the public API does not expose a per-sync "last synced at" time or
    a way to trigger a sync; connection syncs and monitor reruns happen on
    Drata's Autopilot schedule or manually in the web UI.

    Returns:
        Connections with clientType, state, connected flag, and timestamps
    """
    client = get_client()
    result = await client.list_connections()
    return {
        "total": result.get("total"),
        "connections": [
            {
                "id": c.get("id"),
                "clientType": c.get("clientType"),
                "alias": c.get("clientAlias"),
                "state": c.get("state"),
                "connected": c.get("connected"),
                "connectedAt": c.get("connectedAt"),
                "failedAt": c.get("failedAt"),
                "accountId": c.get("accountId"),
            }
            for c in result.get("data", [])
        ],
    }


# ==================== PERSONNEL TOOLS ====================


@mcp.tool()
async def list_personnel(
    employment_status: str | None = None,
) -> dict[str, Any]:
    """List ALL personnel with compliance status.

    Args:
        employment_status: Filter - CURRENT_EMPLOYEE, CURRENT_CONTRACTOR, FORMER_EMPLOYEE, FORMER_CONTRACTOR

    Returns:
        Personnel list with compliance status
    """
    client = get_client()
    result = await client.list_all_personnel(employment_status=employment_status)

    personnel = result.get("data", [])

    # Count active vs inactive (use `or` to handle None values)
    current = sum(1 for p in personnel if (p.get("employmentStatus") or "").startswith("CURRENT"))
    with_failing = sum(1 for p in personnel if (p.get("devicesFailingComplianceCount") or 0) > 0)

    return {
        "total": result.get("total", len(personnel)),
        "summary": {
            "current_employees_contractors": current,
            "with_failing_devices": with_failing,
        },
        "personnel": [
            {
                "id": p.get("id"),
                "email": (p.get("user") or {}).get("email"),
                "name": f"{(p.get('user') or {}).get('firstName', '')} {(p.get('user') or {}).get('lastName', '')}".strip(),
                "employmentStatus": p.get("employmentStatus"),
                "devicesCount": p.get("devicesCount") or 0,
                "devicesFailingCount": p.get("devicesFailingComplianceCount") or 0,
                "startDate": p.get("startDate"),
            }
            for p in personnel
        ],
    }


@mcp.tool()
async def list_personnel_with_issues() -> dict[str, Any]:
    """Get personnel with compliance issues (failing devices).

    Returns:
        Personnel with failing device compliance
    """
    client = get_client()
    result = await client.list_all_personnel()

    personnel = result.get("data", [])

    # Filter to those with issues (use `or` to handle None values)
    with_issues = [
        p for p in personnel
        if (p.get("devicesFailingComplianceCount") or 0) > 0
        and (p.get("employmentStatus") or "").startswith("CURRENT")
    ]

    return {
        "total_with_issues": len(with_issues),
        "message": f"⚠️ {len(with_issues)} personnel with device issues" if with_issues else "✅ All devices compliant",
        "personnel": [
            {
                "id": p.get("id"),
                "email": (p.get("user") or {}).get("email"),
                "name": f"{(p.get('user') or {}).get('firstName', '')} {(p.get('user') or {}).get('lastName', '')}".strip(),
                "employmentStatus": p.get("employmentStatus"),
                "devicesCount": p.get("devicesCount") or 0,
                "devicesFailingCount": p.get("devicesFailingComplianceCount") or 0,
            }
            for p in with_issues
        ],
    }


@mcp.tool()
async def get_personnel_details(personnel_id: int) -> dict[str, Any]:
    """Get detailed personnel compliance information.

    Args:
        personnel_id: Personnel ID

    Returns:
        Full personnel details with compliance checklist
    """
    client = get_client()
    person = await client.get_personnel(personnel_id)

    return {
        "id": person.get("id"),
        "email": person.get("user", {}).get("email"),
        "name": f"{person.get('user', {}).get('firstName', '')} {person.get('user', {}).get('lastName', '')}".strip(),
        "employmentStatus": person.get("employmentStatus"),
        "startDate": person.get("startDate"),
        "separationDate": person.get("separationDate"),
        "devicesCount": person.get("devicesCount", 0),
        "devicesFailingCount": person.get("devicesFailingComplianceCount", 0),
        "complianceChecks": person.get("complianceChecks", {}),
        "complianceTests": person.get("complianceTests", []),
        "devices": person.get("devices", []),
    }


# ==================== POLICIES TOOLS ====================


@mcp.tool()
async def list_policies(limit: int = 50) -> dict[str, Any]:
    """List all company policies.

    Args:
        limit: Max results

    Returns:
        List of policies with version info
    """
    client = get_client()
    result = await client.list_policies(limit=50)

    policies = result.get("data", [])
    return {
        "total": result.get("total", len(policies)),
        "policies": [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "version": p.get("version"),
                "status": p.get("status"),
                "lastUpdatedAt": p.get("updatedAt"),
                "publishedAt": p.get("publishedAt"),
            }
            for p in policies
        ],
    }


@mcp.tool()
async def list_pending_policy_acknowledgments(limit: int = 50) -> dict[str, Any]:
    """Get policies pending user acknowledgment.

    Args:
        limit: Max results

    Returns:
        List of unacknowledged policy assignments
    """
    client = get_client()
    result = await client.list_user_policies(limit=50, acknowledged=False)

    assignments = result.get("data", [])
    return {
        "total_pending": result.get("total", len(assignments)),
        "message": f"📋 {len(assignments)} policy acknowledgments pending" if assignments else "✅ All policies acknowledged",
        "pending": [
            {
                "id": a.get("id"),
                "policyName": a.get("policy", {}).get("name"),
                "policyVersion": a.get("policy", {}).get("version"),
                "userEmail": a.get("user", {}).get("email"),
                "userName": a.get("user", {}).get("name"),
                "assignedAt": a.get("createdAt"),
            }
            for a in assignments
        ],
    }


# ==================== CONNECTIONS TOOLS ====================


@mcp.tool()
async def list_connections(limit: int = 50) -> dict[str, Any]:
    """List all integrations/connections and their status.

    Args:
        limit: Max results

    Returns:
        List of connections with sync status
    """
    client = get_client()
    result = await client.list_connections(limit=50)

    connections = result.get("data", [])

    active = sum(1 for c in connections if c.get("state") == "ACTIVE")
    failed = sum(1 for c in connections if c.get("failedAt"))

    return {
        "total": result.get("total", len(connections)),
        "summary": {
            "active": active,
            "with_failures": failed,
        },
        "connections": [
            {
                "id": c.get("id"),
                "type": c.get("clientType"),
                "state": c.get("state"),
                "connected": c.get("connected"),
                "connectedAt": c.get("connectedAt"),
                "failedAt": c.get("failedAt"),
                "providerTypes": [pt.get("value") for pt in c.get("providerTypes", [])],
            }
            for c in connections
        ],
    }


# ==================== VENDORS TOOLS ====================


@mcp.tool()
async def list_vendors(limit: int = 50) -> dict[str, Any]:
    """List all vendors.

    Args:
        limit: Max results

    Returns:
        List of vendors
    """
    client = get_client()
    result = await client.list_vendors(limit=50)

    vendors = result.get("data", [])
    return {
        "total": result.get("total", len(vendors)),
        "vendors": [
            {
                "id": v.get("id"),
                "name": v.get("name"),
                "website": v.get("website"),
                "status": v.get("status"),
                "riskLevel": v.get("riskLevel"),
                "category": v.get("category"),
            }
            for v in vendors
        ],
    }


# ==================== DEVICES TOOLS ====================


@mcp.tool()
async def list_devices(limit: int = 50) -> dict[str, Any]:
    """List all registered devices.

    Args:
        limit: Max results

    Returns:
        List of devices with compliance status
    """
    client = get_client()
    result = await client.list_devices(limit=50)

    devices = result.get("data", [])
    return {
        "total": result.get("total", len(devices)),
        "devices": [
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "serialNumber": d.get("serialNumber"),
                "platform": d.get("platform"),
                "osVersion": d.get("osVersion"),
                "owner": d.get("user", {}).get("email") if d.get("user") else None,
            }
            for d in devices
        ],
    }


# ==================== EVIDENCE LIBRARY TOOLS ====================


@mcp.tool()
async def list_evidence() -> dict[str, Any]:
    """List ALL evidence in the evidence library.

    Returns evidence documents uploaded to Drata for compliance.

    Returns:
        List of evidence with details and versions
    """
    client = get_client()
    workspace_id = await client.get_workspace_id()
    result = await client.list_all_evidence(workspace_id)

    evidence = result.get("data", [])
    return {
        "total": len(evidence),
        "evidence": [
            {
                "id": e.get("id"),
                "name": e.get("name"),
                "description": e.get("description"),
                "createdAt": e.get("createdAt"),
                "updatedAt": e.get("updatedAt"),
                "versions_count": len(e.get("versions", [])),
                "latest_version": e.get("versions", [{}])[0].get("id") if e.get("versions") else None,
            }
            for e in evidence
        ],
    }


@mcp.tool()
async def list_expiring_evidence(days: int = 30) -> dict[str, Any]:
    """List evidence that hasn't been updated recently and may need renewal.

    Args:
        days: Consider evidence stale if not updated in this many days (default 30)

    Returns:
        Evidence that may need to be renewed
    """
    from datetime import datetime, timedelta, timezone

    client = get_client()
    workspace_id = await client.get_workspace_id()
    result = await client.list_all_evidence(workspace_id)

    evidence = result.get("data", [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stale = []
    for e in evidence:
        updated = e.get("updatedAt", "")
        if updated:
            try:
                updated_time = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if updated_time < cutoff:
                    stale.append({
                        "id": e.get("id"),
                        "name": e.get("name"),
                        "description": e.get("description"),
                        "updatedAt": e.get("updatedAt"),
                        "days_since_update": (datetime.now(timezone.utc) - updated_time).days,
                    })
            except ValueError:
                pass

    # Sort by oldest first
    stale.sort(key=lambda x: x.get("days_since_update", 0), reverse=True)

    return {
        "days_threshold": days,
        "total_stale": len(stale),
        "message": f"⚠️ {len(stale)} evidence items not updated in {days}+ days" if stale else f"✅ All evidence updated within {days} days",
        "stale_evidence": stale,
    }


# ==================== EVENTS TOOLS ====================


@mcp.tool()
async def list_events(
    limit: int = 50,
    category: str | None = None,
) -> dict[str, Any]:
    """List compliance events from the audit log.

    Note: Due to API limitations, events are returned in chronological order (oldest first).

    Args:
        limit: Number of events to return (default 50)
        category: Filter by category - PERSONNEL, CONTROL, MONITOR, CONNECTION, POLICY, VENDOR

    Returns:
        Events with details
    """
    client = get_client()
    result = await client.list_events(limit=min(limit, 50))

    events = result.get("data", [])

    # Filter by category if specified
    if category:
        events = [e for e in events if e.get("category") == category]

    return {
        "total_events": len(events),
        "events": [
            {
                "id": e.get("id"),
                "type": e.get("type"),
                "category": e.get("category"),
                "description": e.get("description"),
                "source": e.get("source"),
                "createdAt": e.get("createdAt"),
                "user": (e.get("user") or {}).get("email"),
            }
            for e in events
        ],
    }


# ==================== ASSETS TOOLS ====================


@mcp.tool()
async def list_assets(
    asset_type: str | None = None,
) -> dict[str, Any]:
    """List all assets in the asset inventory.

    Args:
        asset_type: Filter by type - PHYSICAL, VIRTUAL, CLOUD, DATA, PERSONNEL

    Returns:
        List of assets with details
    """
    client = get_client()
    result = await client.list_assets(limit=50)

    assets = result.get("data", [])

    # Filter by type if specified
    if asset_type:
        assets = [a for a in assets if a.get("assetType") == asset_type]

    return {
        "total": len(assets),
        "assets": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "description": a.get("description"),
                "assetType": a.get("assetType"),
                "assetProvider": a.get("assetProvider"),
                "owner": (a.get("owner") or {}).get("email"),
                "company": a.get("company"),
            }
            for a in assets
        ],
    }


# ==================== USERS TOOLS ====================


@mcp.tool()
async def list_users() -> dict[str, Any]:
    """List all Drata users in your organization.

    Returns:
        List of users with their roles
    """
    client = get_client()
    result = await client._request("GET", "/public/users", params={"limit": 50})

    users = result.get("data", [])
    return {
        "total": result.get("total", len(users)),
        "users": [
            {
                "id": u.get("id"),
                "email": u.get("email"),
                "name": f"{u.get('firstName', '')} {u.get('lastName', '')}".strip(),
                "jobTitle": u.get("jobTitle"),
                "roles": u.get("roles", []),
                "createdAt": u.get("createdAt"),
            }
            for u in users
        ],
    }


# ==================== COMPLIANCE DASHBOARD ====================


@mcp.tool()
async def get_compliance_summary() -> dict[str, Any]:
    """Get overall compliance dashboard summary.

    Returns:
        Aggregated view of compliance status across all areas
    """
    client = get_client()

    # Fetch key metrics (API max limit is 50)
    controls = await client.list_controls(limit=50)
    monitors = await client.list_monitors(limit=50)
    personnel = await client.list_personnel(limit=50)
    connections = await client.list_connections(limit=50)

    # Calculate stats
    monitors_data = monitors.get("data", [])
    failed_monitors = sum(1 for m in monitors_data if m.get("checkResultStatus") == "FAILED")
    passed_monitors = sum(1 for m in monitors_data if m.get("checkResultStatus") == "PASSED")

    personnel_data = personnel.get("data", [])
    current_personnel = sum(1 for p in personnel_data if (p.get("employmentStatus") or "").startswith("CURRENT"))
    personnel_with_issues = sum(1 for p in personnel_data if (p.get("devicesFailingComplianceCount") or 0) > 0 and (p.get("employmentStatus") or "").startswith("CURRENT"))

    connections_data = connections.get("data", [])
    active_connections = sum(1 for c in connections_data if c.get("state") == "ACTIVE")
    failed_connections = sum(1 for c in connections_data if c.get("failedAt"))

    total_issues = failed_monitors + personnel_with_issues + failed_connections

    return {
        "status": "NEEDS_ATTENTION" if total_issues > 0 else "COMPLIANT",
        "total_issues": total_issues,
        "summary": {
            "controls": {
                "total": controls.get("total", 0),
            },
            "monitors": {
                "total": len(monitors_data),
                "passed": passed_monitors,
                "failed": failed_monitors,
                "status": "🔴 CRITICAL" if failed_monitors > 0 else "🟢 OK",
            },
            "personnel": {
                "total": current_personnel,
                "with_device_issues": personnel_with_issues,
                "status": "🟠 WARNING" if personnel_with_issues > 0 else "🟢 OK",
            },
            "connections": {
                "total": len(connections_data),
                "active": active_connections,
                "failed": failed_connections,
                "status": "🔴 CRITICAL" if failed_connections > 0 else "🟢 OK",
            },
        },
        "recommendation": _get_recommendation(failed_monitors, personnel_with_issues, failed_connections),
    }


def _get_recommendation(failed_monitors: int, personnel_issues: int, failed_connections: int) -> str:
    """Generate recommendation based on compliance state."""
    if failed_monitors > 0:
        return f"Priority: Investigate {failed_monitors} failing monitors - automated evidence collection may be broken"
    if failed_connections > 0:
        return f"Priority: Fix {failed_connections} failed connections - integrations are not syncing"
    if personnel_issues > 0:
        return f"Action needed: {personnel_issues} personnel have device compliance issues"
    return "All systems compliant - ready for audit"


# ==================== RESOURCES ====================


@mcp.resource("drata://compliance/summary")
async def compliance_summary_resource() -> str:
    """Current compliance status summary."""
    summary = await get_compliance_summary()
    return f"""# Drata Compliance Summary

**Status**: {summary['status']}
**Total Issues**: {summary['total_issues']}

## Monitors (Automated Tests)
- Total: {summary['summary']['monitors']['total']}
- Passed: {summary['summary']['monitors']['passed']}
- Failed: {summary['summary']['monitors']['failed']} {summary['summary']['monitors']['status']}

## Personnel
- Active: {summary['summary']['personnel']['total']}
- With Device Issues: {summary['summary']['personnel']['with_device_issues']} {summary['summary']['personnel']['status']}

## Connections
- Total: {summary['summary']['connections']['total']}
- Active: {summary['summary']['connections']['active']}
- Failed: {summary['summary']['connections']['failed']} {summary['summary']['connections']['status']}

## Recommendation
{summary['recommendation']}
"""


# ==================== PROMPTS ====================


@mcp.prompt()
def daily_compliance_check() -> str:
    """Start your day with a compliance status check."""
    return """Please give me a complete compliance status report:

1. First, call get_compliance_summary to get the overall status
2. If there are failing monitors, call list_failing_monitors to see details
3. If there are personnel issues, call list_personnel_with_issues
4. Summarize what needs my immediate attention today

Format the response as an actionable task list prioritized by urgency."""


@mcp.prompt()
def prepare_for_audit() -> str:
    """Prepare a comprehensive audit readiness report."""
    return """I need to prepare for an upcoming SOC2 Type II audit. Please:

1. Get the overall compliance summary
2. List ALL failing monitors with details
3. List ALL personnel with device compliance issues
4. List all connections and their status
5. List pending policy acknowledgments

For each issue found, explain:
- What the issue is
- Why it matters for SOC2
- Suggested remediation steps
- Who should own the fix

Organize by priority: Critical → High → Medium → Low"""


@mcp.prompt()
def investigate_monitor(monitor_id: str) -> str:
    """Deep dive into a specific monitor/test failure."""
    return f"""Please investigate monitor ID {monitor_id}:

1. Get the full monitor details using get_monitor_details
2. Explain what this test is checking
3. Show the current status and failure reason if any
4. Provide the recommended remediation steps
5. List which controls are affected

Be thorough - I may need to present this to auditors."""


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
