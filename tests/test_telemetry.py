# SPDX-License-Identifier: MIT
"""Telemetry Schema v2, dual-endpoint fallback, opt-out, and hygiene tests."""
import importlib
import os
import pytest
from bing_webmaster_mcp import telemetry as T


def test_schema_v2_envelope():
    p = T._env_meta()
    required_keys = {
        "schema_version",
        "mcp_server_name",
        "mcp_server_version",
        "$os",
        "python_version",
        "cpu_arch",
        "in_virtual_env",
        "timezone_offset",
        "run_context",
        "agent_name",
        "discovery_channel",
        "install_source",
        "session_id",
        "has_ever_worked",
        "mcp_client_name",
        "mcp_client_version",
        "mcp_protocol_version",
        "client_capabilities",
        "traceparent",
        "trace_id",
        "span_id",
        "$process_person_profile",
    }
    missing = required_keys - set(p.keys())
    assert not missing, f"Missing telemetry envelope fields: {missing}"
    assert p["schema_version"] == 2
    assert p["mcp_server_name"] == "bing-webmaster-mcp"
    assert p["$process_person_profile"] is False


def test_dual_endpoint_fallback():
    assert len(T.GATEWAY_URLS) == 2
    assert T.GATEWAY_URLS[0] == "https://bing-webmaster.builditwithai.xyz/e"
    assert "reachsuren.workers.dev" in T.GATEWAY_URLS[1]


def test_secret_scrubbing():
    dirty = {
        "apikey": "sensitive_12345",
        "indexnow_key": "sensitive_key_abcdef",
        "api_key": "secret",
        "token": "bearer-token",
        "normal_metric": 42,
    }
    clean = T.scrub_props(dirty)
    assert clean["apikey"] == "[REDACTED]"
    assert clean["indexnow_key"] == "[REDACTED]"
    assert clean["api_key"] == "[REDACTED]"
    assert clean["token"] == "[REDACTED]"
    assert clean["normal_metric"] == 42


def test_synthetic_client_exclusion():
    assert T._is_synthetic_client("synthetic-fuzz-runner") is True
    assert T._is_synthetic_client("probe-monitor-agent") is True
    assert T._is_synthetic_client("claude_code") is False
    assert T._is_synthetic_client("cursor") is False


def test_telemetry_opt_out(monkeypatch):
    monkeypatch.setenv("MCP_TELEMETRY_OPT_OUT", "1")
    assert T._telemetry_disabled() is True

    monkeypatch.delenv("MCP_TELEMETRY_OPT_OUT", raising=False)
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    assert T._telemetry_disabled() is True
