# SPDX-License-Identifier: MIT
"""Unit tests for bing-webmaster-mcp server tools and deterministic test beds."""
import json
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from bing_webmaster_mcp import server as S
from .conftest import (
    MOCK_CRAWL_ISSUES,
    MOCK_PAGE_STATS,
    MOCK_QUERY_STATS,
    MOCK_USER_SITES,
)


# ---------------------------------------------------------------------------
# get_user_sites tests
# ---------------------------------------------------------------------------
def test_get_user_sites_missing_key(monkeypatch):
    monkeypatch.delenv("BING_WEBMASTER_API_KEY", raising=False)
    monkeypatch.delenv("BING_API_KEY", raising=False)
    res = S.get_user_sites()
    assert "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN]" in res
    assert "https://www.bing.com/webmasters" in res


def test_get_user_sites_success():
    with patch("bing_webmaster_mcp.server._http_get_json", return_value=MOCK_USER_SITES):
        res = S.get_user_sites(apikey="test-api-key-123")
        data = json.loads(res)
        assert data["total_sites"] == 3
        assert data["verified_count"] == 3
        urls = [s["url"] for s in data["sites"]]
        assert "https://surendranb.com" in urls
        assert "https://freeinference.dev" in urls
        assert "https://builditwithai.xyz" in urls


def test_get_user_sites_auth_error():
    http_err = urllib.error.HTTPError("https://ssl.bing.com", 401, "Unauthorized", {}, None)
    with patch("bing_webmaster_mcp.server._http_get_json", side_effect=http_err):
        res = S.get_user_sites(apikey="invalid-key")
        assert "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN]" in res
        assert "HTTP 401" in res


def test_get_user_sites_transient_error():
    http_err = urllib.error.HTTPError("https://ssl.bing.com", 503, "Service Unavailable", {}, None)
    with patch("bing_webmaster_mcp.server._http_get_json", side_effect=http_err):
        res = S.get_user_sites(apikey="valid-key")
        assert "[TRANSIENT]" in res
        assert "HTTP 503" in res


# ---------------------------------------------------------------------------
# get_query_stats tests (3 deterministic test beds)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("site_url", [
    "https://surendranb.com",
    "https://freeinference.dev",
    "https://builditwithai.xyz",
])
def test_get_query_stats_test_beds(site_url):
    mock_data = MOCK_QUERY_STATS[site_url]
    with patch("bing_webmaster_mcp.server._http_get_json", return_value=mock_data):
        res = S.get_query_stats(site_url, apikey="mock-key")
        data = json.loads(res)
        assert data["site_url"] == site_url
        summary = data["summary"]
        assert summary["total_queries"] == len(mock_data["d"])
        assert summary["total_clicks"] > 0
        assert summary["total_impressions"] > 0
        assert summary["overall_ctr_percent"] >= 0

        # Check date formatting and position scaling
        first_q = data["queries"][0]
        assert "ctr_percent" in first_q
        assert first_q["avg_click_position"] <= 10.0  # scaled down from 10x
        assert first_q["date"].startswith("20")


def test_get_query_stats_invalid_url():
    res = S.get_query_stats("not-a-valid-url", apikey="k")
    assert "[INPUT_FIXABLE]" in res


def test_get_query_stats_missing_key(monkeypatch):
    monkeypatch.delenv("BING_WEBMASTER_API_KEY", raising=False)
    res = S.get_query_stats("https://surendranb.com")
    assert "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN]" in res


# ---------------------------------------------------------------------------
# get_page_stats tests
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("site_url", [
    "https://surendranb.com",
    "https://freeinference.dev",
    "https://builditwithai.xyz",
])
def test_get_page_stats_test_beds(site_url):
    mock_data = MOCK_PAGE_STATS[site_url]
    with patch("bing_webmaster_mcp.server._http_get_json", return_value=mock_data):
        res = S.get_page_stats(site_url, apikey="mock-key")
        data = json.loads(res)
        assert data["site_url"] == site_url
        assert data["summary"]["total_pages"] == len(mock_data["d"])
        assert data["summary"]["total_clicks"] > 0
        first_page = data["pages"][0]
        assert first_page["page_url"].startswith(site_url)


# ---------------------------------------------------------------------------
# get_crawl_issues tests
# ---------------------------------------------------------------------------
def test_get_crawl_issues_surendranb():
    mock_data = MOCK_CRAWL_ISSUES["https://surendranb.com"]
    with patch("bing_webmaster_mcp.server._http_get_json", return_value=mock_data):
        res = S.get_crawl_issues("https://surendranb.com", apikey="mock-key")
        data = json.loads(res)
        assert data["summary"]["total_issues"] == 1
        assert data["summary"]["by_http_code"].get("404") == 1
        assert data["issues"][0]["http_code"] == "404"


def test_get_crawl_issues_freeinference():
    mock_data = MOCK_CRAWL_ISSUES["https://freeinference.dev"]
    with patch("bing_webmaster_mcp.server._http_get_json", return_value=mock_data):
        res = S.get_crawl_issues("https://freeinference.dev", apikey="mock-key")
        data = json.loads(res)
        assert data["summary"]["total_issues"] == 0


def test_get_crawl_issues_builditwithai():
    mock_data = MOCK_CRAWL_ISSUES["https://builditwithai.xyz"]
    with patch("bing_webmaster_mcp.server._http_get_json", return_value=mock_data):
        res = S.get_crawl_issues("https://builditwithai.xyz", apikey="mock-key")
        data = json.loads(res)
        assert data["summary"]["total_issues"] == 1
        assert data["summary"]["by_http_code"].get("500") == 1


# ---------------------------------------------------------------------------
# submit_urls tests (Bing API + IndexNow)
# ---------------------------------------------------------------------------
def test_submit_urls_dual_success():
    post_mock = MagicMock(return_value=(200, '{"d":null}'))
    with patch("bing_webmaster_mcp.server._http_post_json", post_mock):
        res = S.submit_urls(
            site_url="https://surendranb.com",
            urls=["https://surendranb.com/post-1", "https://surendranb.com/post-2"],
            apikey="bing-key",
            indexnow_key="indexnow-key",
        )
        data = json.loads(res)
        assert data["submitted_count"] == 2
        assert data["protocols"]["bing_webmaster_api"]["status"] == "success"
        assert data["protocols"]["indexnow"]["status"] == "success"
        assert post_mock.call_count == 2


def test_submit_urls_missing_keys(monkeypatch):
    monkeypatch.delenv("BING_WEBMASTER_API_KEY", raising=False)
    monkeypatch.delenv("BING_API_KEY", raising=False)
    monkeypatch.delenv("INDEXNOW_KEY", raising=False)
    res = S.submit_urls(
        site_url="https://surendranb.com",
        urls=["https://surendranb.com/post-1"],
    )
    assert "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN]" in res


def test_submit_urls_host_mismatch():
    res = S.submit_urls(
        site_url="https://surendranb.com",
        urls=["https://differentdomain.com/post-1"],
        apikey="key",
    )
    assert "[INPUT_FIXABLE]" in res
    assert "Host mismatch" in res


def test_submit_urls_empty_urls():
    res = S.submit_urls(
        site_url="https://surendranb.com",
        urls=[],
        apikey="key",
    )
    assert "[INPUT_FIXABLE]" in res


# ---------------------------------------------------------------------------
# doctor tests
# ---------------------------------------------------------------------------
def test_doctor_diagnostics(monkeypatch):
    monkeypatch.setenv("BING_WEBMASTER_API_KEY", "mock-1234")
    monkeypatch.setenv("INDEXNOW_KEY", "mock-5678")
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    with patch("bing_webmaster_mcp.server._http_get_json", return_value={"d": []}):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = S.doctor()
            data = json.loads(res)
            assert data["server"] == "bing-webmaster-mcp"
            assert data["diagnostics"]["bing_webmaster_api_key"]["status"] == "configured"
            assert data["diagnostics"]["indexnow_key"]["status"] == "configured"
            assert len(data["diagnostics"]["test_beds"]["configured_sample_domains"]) == 3


# ---------------------------------------------------------------------------
# dynamic skills tests
# ---------------------------------------------------------------------------
def test_skills_list_and_read():
    listing = S.skills_list()
    assert "skills" in listing
    data = json.loads(listing)
    assert "bing-webmaster-audit" in data["skills"]
    assert "indexnow-instant-indexing" in data["skills"]

    # Read existing skill
    content = S.skill_read("bing-webmaster-audit")
    assert "Bing Webmaster Audit Playbook" in content

    # Read unknown skill
    bad = S.skill_read("nonexistent-skill")
    assert "[INPUT_FIXABLE]" in bad
    assert "Available skills" in bad
