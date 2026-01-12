"""Drata API Client."""

from typing import Any

import httpx


class DrataClient:
    """Async client for Drata Public API."""

    BASE_URL = "https://public-api.drata.com"

    def __init__(self, api_key: str, region: str = "us"):
        """Initialize Drata client.

        Args:
            api_key: Drata API key
            region: API region (us, eu, apac)
        """
        self.api_key = api_key
        self.region = region
        self._client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        """Get base URL for region."""
        if self.region == "eu":
            return "https://public-api.eu.drata.com"
        elif self.region == "apac":
            return "https://public-api.apac.drata.com"
        return self.BASE_URL

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make API request."""
        client = await self._get_client()
        response = await client.request(method, path, params=params, json=json)
        response.raise_for_status()
        return response.json()

    # ==================== CONTROLS ====================

    async def list_controls(
        self,
        page: int = 1,
        limit: int = 100,
        status: str | None = None,
        framework_id: int | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List all controls with filters.

        Args:
            page: Page number
            limit: Items per page (max 100)
            status: Filter by status (PASSING, FAILING, NOT_TESTED, etc.)
            framework_id: Filter by framework ID
            search: Search term
        """
        params = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        if framework_id:
            params["frameworkId"] = framework_id
        if search:
            params["q"] = search
        return await self._request("GET", "/public/controls", params=params)

    async def get_control(self, control_id: int) -> dict[str, Any]:
        """Get control by ID."""
        return await self._request("GET", f"/public/controls/{control_id}")

    async def get_control_evidence(self, control_id: int) -> dict[str, Any]:
        """Get external evidence for a control."""
        return await self._request("GET", f"/public/controls/{control_id}/external-evidence")

    # ==================== MONITORS (Automated Tests) ====================

    async def list_monitors(
        self,
        page: int = 1,
        limit: int = 100,
        check_result_status: str | None = None,
    ) -> dict[str, Any]:
        """List automated monitoring tests.

        Args:
            page: Page number
            limit: Items per page
            check_result_status: Filter by status (PASSED, FAILED, NOT_TESTED)
        """
        params = {"page": page, "limit": limit}
        if check_result_status:
            params["checkResultStatus"] = check_result_status
        return await self._request("GET", "/public/monitors", params=params)

    async def get_monitor(self, monitor_id: int) -> dict[str, Any]:
        """Get monitor by ID."""
        return await self._request("GET", f"/public/monitors/{monitor_id}")

    # ==================== PERSONNEL ====================

    async def list_personnel(
        self,
        page: int = 1,
        limit: int = 100,
        employment_status: str | None = None,
    ) -> dict[str, Any]:
        """List all personnel.

        Args:
            page: Page number
            limit: Items per page
            employment_status: Filter (CURRENT_EMPLOYEE, CURRENT_CONTRACTOR, FORMER, etc.)
        """
        params = {"page": page, "limit": limit}
        if employment_status:
            params["employmentStatus"] = employment_status
        return await self._request("GET", "/public/personnel", params=params)

    async def get_personnel(self, personnel_id: int) -> dict[str, Any]:
        """Get personnel by ID."""
        return await self._request("GET", f"/public/personnel/{personnel_id}")

    async def get_personnel_by_email(self, email: str) -> dict[str, Any]:
        """Find personnel by email."""
        result = await self._request("GET", "/public/personnel", params={"email": email})
        if result.get("data"):
            return result["data"][0]
        raise ValueError(f"Personnel not found: {email}")

    # ==================== POLICIES ====================

    async def list_policies(
        self,
        page: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List all policies."""
        params = {"page": page, "limit": limit}
        return await self._request("GET", "/public/policies", params=params)

    async def get_policy(self, policy_id: int) -> dict[str, Any]:
        """Get policy by ID."""
        return await self._request("GET", f"/public/policies/{policy_id}")

    async def list_user_policies(
        self,
        page: int = 1,
        limit: int = 100,
        acknowledged: bool | None = None,
    ) -> dict[str, Any]:
        """List user policy assignments.

        Args:
            page: Page number
            limit: Items per page
            acknowledged: Filter by acknowledgment status
        """
        params = {"page": page, "limit": limit}
        if acknowledged is not None:
            params["acknowledged"] = str(acknowledged).lower()
        return await self._request("GET", "/public/user-policies", params=params)

    # ==================== CONNECTIONS ====================

    async def list_connections(
        self,
        page: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List all integrations/connections."""
        params = {"page": page, "limit": limit}
        return await self._request("GET", "/public/connections", params=params)

    # ==================== VENDORS ====================

    async def list_vendors(
        self,
        page: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List all vendors."""
        params = {"page": page, "limit": limit}
        return await self._request("GET", "/public/vendors", params=params)

    async def get_vendor(self, vendor_id: int) -> dict[str, Any]:
        """Get vendor by ID."""
        return await self._request("GET", f"/public/vendors/{vendor_id}")

    # ==================== DEVICES ====================

    async def list_devices(
        self,
        page: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List all devices."""
        params = {"page": page, "limit": limit}
        return await self._request("GET", "/public/devices", params=params)

    # ==================== ASSETS ====================

    async def list_assets(
        self,
        page: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List all assets."""
        params = {"page": page, "limit": limit}
        return await self._request("GET", "/public/assets", params=params)

    # ==================== EVENTS ====================

    async def list_events(
        self,
        page: int = 1,
        limit: int = 100,
        event_type: str | None = None,
    ) -> dict[str, Any]:
        """List audit events.

        Args:
            page: Page number
            limit: Items per page
            event_type: Filter by event type
        """
        params = {"page": page, "limit": limit}
        if event_type:
            params["eventType"] = event_type
        return await self._request("GET", "/public/events", params=params)
