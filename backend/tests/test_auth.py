"""
Auth middleware tests for auth.py.

Tests the BearerTokenAuthMiddleware and verify_token function.
"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, patch

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from auth import BearerTokenAuthMiddleware, verify_token, is_excluded_path


class TestIsExcludedPath:
    """Tests for the path exclusion helper."""

    def test_exact_match(self):
        assert is_excluded_path("/health", ["/health"]) is True

    def test_prefix_match(self):
        assert is_excluded_path("/health/ready", ["/health"]) is True

    def test_no_match(self):
        assert is_excluded_path("/api/data", ["/health"]) is False

    def test_empty_excludes(self):
        assert is_excluded_path("/anything", []) is False

    def test_root_exclusion(self):
        assert is_excluded_path("/anything", ["/"]) is True


class TestBearerTokenMiddleware:
    """Tests for the BearerTokenAuthMiddleware ASGI middleware."""

    def _make_scope(self, path="/api/test", headers=None):
        scope_headers = []
        if headers:
            for key, value in headers.items():
                scope_headers.append(
                    (key.lower().encode(), value.encode())
                )
        return {
            "type": "http",
            "path": path,
            "headers": scope_headers,
        }

    @patch.dict(os.environ, {"API_TOKEN": ""}, clear=False)
    async def test_no_token_configured_allows_all(self):
        """When API_TOKEN is empty, all requests pass through."""
        app_mock = AsyncMock()
        middleware = BearerTokenAuthMiddleware(app_mock)

        scope = self._make_scope()
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app_mock.assert_called_once()

    @patch.dict(os.environ, {"API_TOKEN": "secret123"}, clear=False)
    async def test_health_endpoint_bypasses_auth(self):
        """Excluded paths bypass auth."""
        app_mock = AsyncMock()
        middleware = BearerTokenAuthMiddleware(
            app_mock, excluded_paths=["/health"]
        )

        scope = self._make_scope(path="/health")
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app_mock.assert_called_once()

    @patch.dict(os.environ, {"API_TOKEN": "secret123"}, clear=False)
    async def test_valid_token_passes(self):
        """Correct Bearer token allows the request."""
        app_mock = AsyncMock()
        middleware = BearerTokenAuthMiddleware(app_mock)

        scope = self._make_scope(
            headers={"authorization": "Bearer secret123"}
        )
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app_mock.assert_called_once()

    @patch.dict(os.environ, {"API_TOKEN": "secret123"}, clear=False)
    async def test_invalid_token_rejected(self):
        """Wrong token returns 401 (app not called)."""
        app_mock = AsyncMock()
        middleware = BearerTokenAuthMiddleware(app_mock)

        scope = self._make_scope(
            headers={"authorization": "Bearer wrongtoken"}
        )
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app_mock.assert_not_called()

    @patch.dict(os.environ, {"API_TOKEN": "secret123"}, clear=False)
    async def test_missing_token_rejected(self):
        """No Authorization header returns 401."""
        app_mock = AsyncMock()
        middleware = BearerTokenAuthMiddleware(app_mock)

        scope = self._make_scope()
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app_mock.assert_not_called()

    @patch.dict(os.environ, {"API_TOKEN": "secret123"}, clear=False)
    async def test_non_http_passes_through(self):
        """Non-HTTP scopes (websocket, lifespan) pass through."""
        app_mock = AsyncMock()
        middleware = BearerTokenAuthMiddleware(app_mock)

        scope = {"type": "lifespan"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app_mock.assert_called_once()

    @patch.dict(os.environ, {"API_TOKEN": "secret123"}, clear=False)
    async def test_bearer_prefix_required(self):
        """Authorization without 'Bearer ' prefix is rejected."""
        app_mock = AsyncMock()
        middleware = BearerTokenAuthMiddleware(app_mock)

        scope = self._make_scope(
            headers={"authorization": "Token secret123"}
        )
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app_mock.assert_not_called()
