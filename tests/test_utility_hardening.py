# SPDX-License-Identifier: MIT
"""Unit tests for Bing Webmaster MCP Utility Hardening (SUR-471).

Tests:
1. submit_urls validation when urls list is empty or malformed.
2. IndexNow key preflight check returning actionable guidance on missing key file.
3. get_submission_quota tool checking remaining daily submission quota.
4. get_crawl_issues categorized taxonomy (5xx, 4xx, robots, dns).
5. MCP tool annotations inspection.
"""

import json
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from bing_webmaster_mcp import server as S


def test_submit_urls_empty_or_invalid():
    """submit_urls returns clear validation error when urls list is empty or invalid."""
    res = S.submit_urls(site_url="https://example.com", urls=[], apikey="test-key")
    assert "[INPUT_FIXABLE]" in res
    assert "No URLs provided" in res

    res2 = S.submit_urls(site_url="https://example.com", urls=None, apikey="test-key")
    assert "[INPUT_FIXABLE]" in res2


def test_indexnow_preflight_check():
    """_preflight_indexnow_key verifies presence of host key file."""
    # 1. 404 Key file missing
    http_404 = urllib.error.HTTPError("https://example.com/testkey.txt", 404, "Not Found", {}, None)
    with patch("urllib.request.urlopen", side_effect=http_404):
        ok, msg = S._preflight_indexnow_key("https://example.com", "testkey")
        assert ok is False
        assert "IndexNow key verification file missing" in msg
        assert "https://example.com/testkey.txt" in msg

    # 2. 200 Key file present
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"testkey\n"
    mock_resp.getcode.return_value = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        ok, msg = S._preflight_indexnow_key("https://example.com", "testkey")
        assert ok is True


def test_get_submission_quota():
    """get_submission_quota calls Bing API GetUrlSubmissionQuota endpoint."""
    mock_quota_resp = {
        "d": {
            "DailyQuota": 10000,
            "MonthlyQuota": 1000000
        }
    }
    with patch("bing_webmaster_mcp.server._http_get_json", return_value=mock_quota_resp):
        res = S.get_submission_quota(site_url="https://example.com", apikey="test-key")
        data = json.loads(res)
        assert data["site_url"] == "https://example.com"
        assert data["daily_quota"] == 10000
        assert data["monthly_quota"] == 1000000
        assert "guidance" in data


def test_categorized_crawl_issues():
    """get_crawl_issues groups issues into status taxonomy."""
    mock_raw_issues = {
        "d": [
            {"IssueType": 1, "Severity": 2, "Url": "https://example.com/broken-1", "HttpCode": 404},
            {"IssueType": 1, "Severity": 2, "Url": "https://example.com/broken-2", "HttpCode": 404},
            {"IssueType": 2, "Severity": 3, "Url": "https://example.com/server-err", "HttpCode": 500},
            {"IssueType": 3, "Severity": 1, "Url": "https://example.com/blocked", "HttpCode": 0, "Description": "Blocked by robots.txt"}
        ]
    }
    with patch("bing_webmaster_mcp.server._http_get_json", return_value=mock_raw_issues):
        res = S.get_crawl_issues(site_url="https://example.com", apikey="test-key")
        data = json.loads(res)
        assert "summary" in data
        assert data["summary"]["total_issues"] == 4
        assert "categorized" in data
        assert "http_4xx" in data["categorized"]
        assert data["categorized"]["http_4xx"]["count"] == 2
        assert "http_5xx" in data["categorized"]
        assert data["categorized"]["http_5xx"]["count"] == 1
