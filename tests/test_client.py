"""Tests for Drata API client."""

import pytest
import respx
from httpx import Response

from drata_mcp.client import DrataClient


@pytest.fixture
def client():
    """Create test client."""
    return DrataClient(api_key="test-key", region="us")


class TestDrataClientInit:
    """Test client initialization."""

    def test_default_region(self):
        client = DrataClient("key")
        assert client.region == "us"
        assert client.base_url == "https://public-api.drata.com"

    def test_eu_region(self):
        client = DrataClient("key", region="eu")
        assert client.base_url == "https://public-api.eu.drata.com"

    def test_apac_region(self):
        client = DrataClient("key", region="apac")
        assert client.base_url == "https://public-api.apac.drata.com"


class TestListControls:
    """Test controls endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_controls_success(self, client):
        respx.get("https://public-api.drata.com/public/controls").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "name": "Control 1", "code": "DCF-1", "status": "PASSING"},
                    {"id": 2, "name": "Control 2", "code": "DCF-2", "status": "FAILING"},
                ],
                "total": 2,
                "page": 1,
                "limit": 50,
            })
        )

        result = await client.list_controls(limit=50)

        assert result["total"] == 2
        assert len(result["data"]) == 2
        assert result["data"][0]["code"] == "DCF-1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_controls_with_search(self, client):
        route = respx.get("https://public-api.drata.com/public/controls").mock(
            return_value=Response(200, json={"data": [], "total": 0})
        )

        await client.list_controls(search="encryption")

        assert route.called
        assert "q=encryption" in str(route.calls[0].request.url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_control(self, client):
        respx.get("https://public-api.drata.com/public/controls/123").mock(
            return_value=Response(200, json={
                "id": 123,
                "name": "Test Control",
                "code": "DCF-123",
                "status": "PASSING",
                "description": "Test description",
            })
        )

        result = await client.get_control(123)

        assert result["id"] == 123
        assert result["code"] == "DCF-123"


class TestListMonitors:
    """Test monitors endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_monitors_success(self, client):
        respx.get("https://public-api.drata.com/public/monitors").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "name": "Monitor 1", "checkResultStatus": "PASSED", "priority": "HIGH"},
                    {"id": 2, "name": "Monitor 2", "checkResultStatus": "FAILED", "priority": "LOW"},
                ],
                "total": 2,
            })
        )

        result = await client.list_monitors(limit=50)

        assert result["total"] == 2
        assert result["data"][0]["checkResultStatus"] == "PASSED"
        assert result["data"][1]["checkResultStatus"] == "FAILED"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_monitors_with_status_filter(self, client):
        route = respx.get("https://public-api.drata.com/public/monitors").mock(
            return_value=Response(200, json={"data": [], "total": 0})
        )

        await client.list_monitors(check_result_status="FAILED")

        assert "checkResultStatus=FAILED" in str(route.calls[0].request.url)


class TestListPersonnel:
    """Test personnel endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_personnel_success(self, client):
        respx.get("https://public-api.drata.com/public/personnel").mock(
            return_value=Response(200, json={
                "data": [
                    {
                        "id": 1,
                        "employmentStatus": "CURRENT_EMPLOYEE",
                        "user": {"email": "test@example.com", "firstName": "John", "lastName": "Doe"},
                        "devicesFailingComplianceCount": 0,
                    },
                ],
                "total": 1,
            })
        )

        result = await client.list_personnel(limit=50)

        assert result["total"] == 1
        assert result["data"][0]["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_personnel_by_email(self, client):
        respx.get("https://public-api.drata.com/public/personnel").mock(
            return_value=Response(200, json={
                "data": [{"id": 1, "user": {"email": "test@example.com"}}],
            })
        )

        result = await client.get_personnel_by_email("test@example.com")

        assert result["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_personnel_by_email_not_found(self, client):
        respx.get("https://public-api.drata.com/public/personnel").mock(
            return_value=Response(200, json={"data": []})
        )

        with pytest.raises(ValueError, match="Personnel not found"):
            await client.get_personnel_by_email("notfound@example.com")


class TestListPolicies:
    """Test policies endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_policies_success(self, client):
        respx.get("https://public-api.drata.com/public/policies").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "name": "Security Policy", "version": 3, "status": "PUBLISHED"},
                ],
                "total": 1,
            })
        )

        result = await client.list_policies(limit=50)

        assert result["total"] == 1
        assert result["data"][0]["name"] == "Security Policy"


class TestListConnections:
    """Test connections endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_connections_success(self, client):
        respx.get("https://public-api.drata.com/public/connections").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "clientType": "GITHUB", "state": "ACTIVE", "connected": True},
                    {"id": 2, "clientType": "AWS", "state": "ACTIVE", "connected": True},
                ],
                "total": 2,
            })
        )

        result = await client.list_connections(limit=50)

        assert result["total"] == 2
        assert result["data"][0]["clientType"] == "GITHUB"


class TestListVendors:
    """Test vendors endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_vendors_success(self, client):
        respx.get("https://public-api.drata.com/public/vendors").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": 1, "name": "Vendor A", "riskLevel": "LOW"},
                ],
                "total": 1,
            })
        )

        result = await client.list_vendors(limit=50)

        assert result["total"] == 1
        assert result["data"][0]["name"] == "Vendor A"
