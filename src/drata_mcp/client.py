"""Drata API Client."""

from typing import Any, Callable, Coroutine

import httpx

# Drata API max limit per request
MAX_PAGE_SIZE = 50


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

    async def _paginate_all(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch all pages and combine results.

        Returns combined data with total count.
        """
        params = params or {}
        params["limit"] = MAX_PAGE_SIZE
        params["page"] = 1

        all_data: list[dict[str, Any]] = []
        total = 0

        while True:
            result = await self._request("GET", path, params=params)
            data = result.get("data", [])
            total = result.get("total", total)

            all_data.extend(data)

            # Stop if we got fewer than the limit (last page)
            if len(data) < MAX_PAGE_SIZE:
                break

            # Stop if we have all items
            if len(all_data) >= total:
                break

            params["page"] += 1

        return {"data": all_data, "total": total}

    # ==================== CONTROLS ====================

    async def list_controls(
        self,
        page: int = 1,
        limit: int = 50,
        status: str | None = None,
        framework_id: int | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List controls (single page).

        Args:
            page: Page number
            limit: Items per page (max 50)
            status: Filter by status
            framework_id: Filter by framework ID
            search: Search term
        """
        params = {"page": page, "limit": min(limit, MAX_PAGE_SIZE)}
        if status:
            params["status"] = status
        if framework_id:
            params["frameworkId"] = framework_id
        if search:
            params["q"] = search
        return await self._request("GET", "/public/controls", params=params)

    async def list_all_controls(
        self,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List ALL controls (auto-paginated).

        Args:
            search: Search term
        """
        params = {}
        if search:
            params["q"] = search
        return await self._paginate_all("/public/controls", params)

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
        limit: int = 50,
        check_result_status: str | None = None,
    ) -> dict[str, Any]:
        """List monitors (single page).

        Args:
            page: Page number
            limit: Items per page (max 50)
            check_result_status: Filter by status (PASSED, FAILED, NOT_TESTED)
        """
        params = {"page": page, "limit": min(limit, MAX_PAGE_SIZE)}
        if check_result_status:
            params["checkResultStatus"] = check_result_status
        return await self._request("GET", "/public/monitors", params=params)

    async def list_all_monitors(
        self,
        check_result_status: str | None = None,
        control_id: int | None = None,
    ) -> dict[str, Any]:
        """List ALL monitors (auto-paginated).

        Args:
            check_result_status: Filter by status (PASSED, FAILED, NOT_TESTED)
            control_id: Filter to monitors mapped to a specific control
        """
        params: dict[str, Any] = {}
        if check_result_status:
            params["checkResultStatus"] = check_result_status
        if control_id:
            params["controlId"] = control_id
        return await self._paginate_all("/public/monitors", params)

    async def get_monitor(self, workspace_id: int, test_id: int) -> dict[str, Any]:
        """Get monitoring test details by test ID (API v2).

        Note: the v1 `GET /public/monitors/{id}` endpoint does not exist
        (v1 only supports listing); details live under the workspace-scoped
        v2 path. `test_id` is the monitor's `testId` field, not its `id`.
        """
        return await self._request(
            "GET", f"/public/v2/workspaces/{workspace_id}/monitoring-tests/{test_id}"
        )

    async def list_monitor_failures(
        self,
        workspace_id: int,
        test_id: int,
        page: int = 1,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List the resources currently failing a monitoring test (API v2).

        Args:
            workspace_id: Workspace ID
            test_id: The monitor's testId
            page: Page number
            limit: Items per page (max 50)
        """
        params = {"page": page, "limit": min(limit, MAX_PAGE_SIZE)}
        return await self._request(
            "GET",
            f"/public/v2/workspaces/{workspace_id}/monitoring-tests/{test_id}/failures",
            params=params,
        )

    # ==================== PERSONNEL ====================

    async def list_personnel(
        self,
        page: int = 1,
        limit: int = 50,
        employment_status: str | None = None,
    ) -> dict[str, Any]:
        """List personnel (single page).

        Args:
            page: Page number
            limit: Items per page (max 50)
            employment_status: Filter (CURRENT_EMPLOYEE, CURRENT_CONTRACTOR, FORMER, etc.)
        """
        params = {"page": page, "limit": min(limit, MAX_PAGE_SIZE)}
        if employment_status:
            params["employmentStatus"] = employment_status
        return await self._request("GET", "/public/personnel", params=params)

    async def list_all_personnel(
        self,
        employment_status: str | None = None,
    ) -> dict[str, Any]:
        """List ALL personnel (auto-paginated).

        Args:
            employment_status: Filter (CURRENT_EMPLOYEE, CURRENT_CONTRACTOR, FORMER, etc.)
        """
        params = {}
        if employment_status:
            params["employmentStatus"] = employment_status
        return await self._paginate_all("/public/personnel", params)

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

    # ==================== CONTROL NOTES ====================

    async def list_control_notes(
        self,
        workspace_id: int,
        control_id: int,
    ) -> dict[str, Any]:
        """List notes on a control (API v2)."""
        return await self._request(
            "GET",
            f"/public/v2/workspaces/{workspace_id}/controls/{control_id}/notes",
        )

    async def create_control_note(
        self,
        workspace_id: int,
        control_id: int,
        comment: str,
    ) -> dict[str, Any]:
        """Create a note on a control (API v2).

        Args:
            workspace_id: Workspace ID
            control_id: Control ID (numeric id, not DCF code)
            comment: Note text (max 191 characters)
        """
        return await self._request(
            "POST",
            f"/public/v2/workspaces/{workspace_id}/controls/{control_id}/notes",
            json={"comment": comment},
        )

    # ==================== CONTROL OWNERS ====================

    async def list_control_owners(
        self,
        workspace_id: int,
        control_id: int,
    ) -> dict[str, Any]:
        """List owners of a control (API v2)."""
        return await self._request(
            "GET",
            f"/public/v2/workspaces/{workspace_id}/controls/{control_id}/owners",
        )

    async def add_control_owner(
        self,
        workspace_id: int,
        control_id: int,
        owner_id: int,
    ) -> dict[str, Any]:
        """Add an owner to a control (API v2).

        Args:
            workspace_id: Workspace ID
            control_id: Control ID (numeric id, not DCF code)
            owner_id: Drata user ID (not personnel ID)
        """
        return await self._request(
            "POST",
            f"/public/v2/workspaces/{workspace_id}/controls/{control_id}/owners",
            json={"ownerId": owner_id},
        )

    async def find_user_by_email(self, email: str) -> dict[str, Any]:
        """Find a Drata user (not personnel) by email address."""
        result = await self._paginate_all("/public/users")
        for u in result.get("data", []):
            if (u.get("email") or "").lower() == email.lower():
                return u
        raise ValueError(f"User not found: {email}")

    # ==================== EVIDENCE LIBRARY (WRITE) ====================

    async def create_evidence(
        self,
        workspace_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create an Evidence Library item (API v2).

        Payload fields: name (required); optional description, controlIds,
        url/ticketUrl/base64File (one artifact source max — when provided,
        renewalScheduleType, filedAt, and ownerId become required),
        renewalDate, implementationGuidance.
        """
        return await self._request(
            "POST",
            f"/public/v2/workspaces/{workspace_id}/evidence-library",
            json=payload,
        )

    async def update_evidence(
        self,
        workspace_id: int,
        evidence_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an Evidence Library item (API v2), e.g. to link controlIds."""
        return await self._request(
            "PUT",
            f"/public/v2/workspaces/{workspace_id}/evidence-library/{evidence_id}",
            json=payload,
        )

    # ==================== WORKSPACES ====================

    _workspace_id: int | None = None

    async def get_workspace_id(self) -> int:
        """Get the primary workspace ID (cached after first call)."""
        if self._workspace_id is not None:
            return self._workspace_id
        result = await self._request("GET", "/public/workspaces", params={"limit": 1})
        if result.get("data"):
            self._workspace_id = result["data"][0]["id"]
            return self._workspace_id
        raise ValueError("No workspace found")

    # ==================== EVIDENCE LIBRARY ====================

    async def list_evidence(
        self,
        workspace_id: int,
        page: int = 1,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List evidence library items.

        Args:
            workspace_id: Workspace ID
            page: Page number
            limit: Items per page (max 50)
        """
        params = {"page": page, "limit": min(limit, MAX_PAGE_SIZE)}
        return await self._request(
            "GET",
            f"/public/workspaces/{workspace_id}/evidence-library",
            params=params,
        )

    async def list_all_evidence(self, workspace_id: int) -> dict[str, Any]:
        """List ALL evidence library items (auto-paginated).

        Args:
            workspace_id: Workspace ID
        """
        return await self._paginate_all(
            f"/public/workspaces/{workspace_id}/evidence-library"
        )

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
