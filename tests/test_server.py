"""Tests for MCP server tools."""

import pytest
import respx
from httpx import Response

# Reset client before importing server
import drata_mcp.server as server_module


@pytest.fixture(autouse=True)
def reset_client(mock_api_key):
    """Reset global client before each test."""
    server_module._client = None
    yield
    server_module._client = None


class TestListControls:
    """Test list_controls tool."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_controls_formats_response(self):
        respx.get("https://public-api.drata.com/public/controls").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "name": "Control 1", "code": "DCF-1", "isMonitored": True, "hasEvidence": True, "hasOwner": True, "isReady": True, "frameworkTags": ["SOC 2"]},
                    {"id": 2, "name": "Control 2", "code": "DCF-2", "isMonitored": False, "hasEvidence": False, "hasOwner": True, "isReady": True, "frameworkTags": ["SOC 2"]},
                ],
                "total": 2,
            })
        )

        result = await server_module.list_controls()

        assert result["total"] == 2
        assert result["showing"] == 2
        assert result["controls"][0]["code"] == "DCF-1"
        assert result["controls"][0]["status"] == "PASSING"
        assert result["controls"][1]["status"] == "NEEDS_EVIDENCE"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_controls_only_issues(self):
        respx.get("https://public-api.drata.com/public/controls").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "name": "Good", "code": "DCF-1", "isMonitored": True, "hasEvidence": True, "hasOwner": True, "isReady": True},
                    {"id": 2, "name": "Needs Evidence", "code": "DCF-2", "isMonitored": False, "hasEvidence": False, "hasOwner": True, "isReady": True},
                    {"id": 3, "name": "Not Ready", "code": "DCF-3", "isMonitored": False, "hasEvidence": False, "hasOwner": False, "isReady": False},
                ],
                "total": 3,
            })
        )

        result = await server_module.list_controls(only_issues=True)

        assert result["showing"] == 2  # Only the 2 with issues
        assert result["summary"]["not_ready"] == 1
        assert result["summary"]["needs_evidence"] == 1


class TestListMonitors:
    """Test list_monitors tool."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_monitors_with_summary(self):
        respx.get("https://public-api.drata.com/public/monitors").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "name": "Monitor 1", "checkResultStatus": "PASSED", "priority": "HIGH", "lastCheck": "2024-01-01", "checkStatus": "ENABLED"},
                    {"id": 2, "name": "Monitor 2", "checkResultStatus": "FAILED", "priority": "LOW", "lastCheck": "2024-01-01", "checkStatus": "ENABLED"},
                    {"id": 3, "name": "Monitor 3", "checkResultStatus": "PASSED", "priority": "HIGH", "lastCheck": "2024-01-01", "checkStatus": "ENABLED"},
                ],
                "total": 3,
            })
        )

        result = await server_module.list_monitors()

        assert result["total"] == 3
        assert result["summary"]["passed"] == 2
        assert result["summary"]["failed"] == 1
        assert result["summary"]["not_tested"] == 0


class TestListFailingMonitors:
    """Test list_failing_monitors tool."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_filters_only_failed(self):
        respx.get("https://public-api.drata.com/public/monitors").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "name": "Passing", "checkResultStatus": "PASSED", "priority": "HIGH", "lastCheck": "2024-01-01", "description": "", "controls": []},
                    {"id": 2, "name": "Failing", "checkResultStatus": "FAILED", "priority": "LOW", "lastCheck": "2024-01-01", "description": "Test desc", "controls": [{"code": "DCF-1"}]},
                ],
                "total": 2,
            })
        )

        result = await server_module.list_failing_monitors()

        assert result["total_failed"] == 1
        assert len(result["failing_monitors"]) == 1
        assert result["failing_monitors"][0]["name"] == "Failing"
        assert result["failing_monitors"][0]["controls"] == ["DCF-1"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_message_when_all_passing(self):
        respx.get("https://public-api.drata.com/public/monitors").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "name": "Passing", "checkResultStatus": "PASSED", "priority": "HIGH", "lastCheck": "2024-01-01", "description": "", "controls": []},
                ],
                "total": 1,
            })
        )

        result = await server_module.list_failing_monitors()

        assert result["total_failed"] == 0
        assert "All tests passing" in result["message"]


class TestListPersonnel:
    """Test list_personnel tool."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_personnel_summary(self):
        respx.get("https://public-api.drata.com/public/personnel").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "employmentStatus": "CURRENT_EMPLOYEE", "user": {"email": "a@test.com", "firstName": "A", "lastName": "B"}, "devicesCount": 1, "devicesFailingComplianceCount": 0, "startDate": "2024-01-01"},
                    {"id": 2, "employmentStatus": "CURRENT_CONTRACTOR", "user": {"email": "b@test.com", "firstName": "C", "lastName": "D"}, "devicesCount": 1, "devicesFailingComplianceCount": 1, "startDate": "2024-01-01"},
                    {"id": 3, "employmentStatus": "FORMER", "user": {"email": "c@test.com", "firstName": "E", "lastName": "F"}, "devicesCount": 0, "devicesFailingComplianceCount": 0, "startDate": "2024-01-01"},
                ],
                "total": 3,
            })
        )

        result = await server_module.list_personnel()

        assert result["total"] == 3
        assert result["summary"]["current_employees_contractors"] == 2
        assert result["summary"]["with_failing_devices"] == 1


class TestListPersonnelWithIssues:
    """Test list_personnel_with_issues tool."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_filters_current_with_issues(self):
        respx.get("https://public-api.drata.com/public/personnel").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "employmentStatus": "CURRENT_EMPLOYEE", "user": {"email": "a@test.com", "firstName": "A", "lastName": "B"}, "devicesCount": 1, "devicesFailingComplianceCount": 2},
                    {"id": 2, "employmentStatus": "CURRENT_EMPLOYEE", "user": {"email": "b@test.com", "firstName": "C", "lastName": "D"}, "devicesCount": 1, "devicesFailingComplianceCount": 0},
                    {"id": 3, "employmentStatus": "FORMER", "user": {"email": "c@test.com", "firstName": "E", "lastName": "F"}, "devicesCount": 1, "devicesFailingComplianceCount": 1},
                ],
                "total": 3,
            })
        )

        result = await server_module.list_personnel_with_issues()

        assert result["total_with_issues"] == 1
        assert result["personnel"][0]["email"] == "a@test.com"


class TestListPolicies:
    """Test list_policies tool."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_policies(self):
        respx.get("https://public-api.drata.com/public/policies").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "name": "Policy A", "version": 3, "status": "PUBLISHED", "updatedAt": "2024-01-01", "publishedAt": "2024-01-01"},
                ],
                "total": 1,
            })
        )

        result = await server_module.list_policies()

        assert result["total"] == 1
        assert result["policies"][0]["version"] == 3


class TestListConnections:
    """Test list_connections tool."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_connections_summary(self):
        respx.get("https://public-api.drata.com/public/connections").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "clientType": "GITHUB", "state": "ACTIVE", "connected": True, "connectedAt": "2024-01-01", "failedAt": None, "providerTypes": [{"value": "VERSION_CONTROL"}]},
                    {"id": 2, "clientType": "AWS", "state": "INACTIVE", "connected": False, "connectedAt": "2024-01-01", "failedAt": "2024-01-02", "providerTypes": [{"value": "INFRASTRUCTURE"}]},
                ],
                "total": 2,
            })
        )

        result = await server_module.list_connections()

        assert result["total"] == 2
        assert result["summary"]["active"] == 1
        assert result["summary"]["with_failures"] == 1
        assert result["connections"][0]["providerTypes"] == ["VERSION_CONTROL"]


class TestGetComplianceSummary:
    """Test get_compliance_summary tool."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_aggregates_all_metrics(self):
        respx.get("https://public-api.drata.com/public/controls").mock(
            return_value=Response(200, json={"data": [], "total": 100})
        )
        respx.get("https://public-api.drata.com/public/monitors").mock(
            return_value=Response(200, json={
                "data": [
                    {"checkResultStatus": "PASSED"},
                    {"checkResultStatus": "FAILED"},
                ],
                "total": 2,
            })
        )
        respx.get("https://public-api.drata.com/public/personnel").mock(
            return_value=Response(200, json={
                "data": [
                    {"employmentStatus": "CURRENT_EMPLOYEE", "devicesFailingComplianceCount": 0},
                    {"employmentStatus": "CURRENT_EMPLOYEE", "devicesFailingComplianceCount": 1},
                ],
                "total": 2,
            })
        )
        respx.get("https://public-api.drata.com/public/connections").mock(
            return_value=Response(200, json={
                "data": [
                    {"state": "ACTIVE", "failedAt": None},
                ],
                "total": 1,
            })
        )

        result = await server_module.get_compliance_summary()

        assert result["status"] == "NEEDS_ATTENTION"
        assert result["total_issues"] == 2  # 1 failed monitor + 1 personnel with issues
        assert result["summary"]["controls"]["total"] == 100
        assert result["summary"]["monitors"]["failed"] == 1
        assert result["summary"]["personnel"]["with_device_issues"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_compliant_status_when_no_issues(self):
        respx.get("https://public-api.drata.com/public/controls").mock(
            return_value=Response(200, json={"data": [], "total": 10})
        )
        respx.get("https://public-api.drata.com/public/monitors").mock(
            return_value=Response(200, json={
                "data": [{"checkResultStatus": "PASSED"}],
                "total": 1,
            })
        )
        respx.get("https://public-api.drata.com/public/personnel").mock(
            return_value=Response(200, json={
                "data": [{"employmentStatus": "CURRENT_EMPLOYEE", "devicesFailingComplianceCount": 0}],
                "total": 1,
            })
        )
        respx.get("https://public-api.drata.com/public/connections").mock(
            return_value=Response(200, json={
                "data": [{"state": "ACTIVE", "failedAt": None}],
                "total": 1,
            })
        )

        result = await server_module.get_compliance_summary()

        assert result["status"] == "COMPLIANT"
        assert result["total_issues"] == 0
        assert "ready for audit" in result["recommendation"]
