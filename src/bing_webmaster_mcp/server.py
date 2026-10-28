# SPDX-License-Identifier: MIT
"""Bing Webmaster Tools & IndexNow API MCP Server.

Provides search performance analytics, page traffic, crawl issue inspection,
and real-time batch URL submission via IndexNow & Bing Webmaster API.
"""
from __future__ import annotations

import datetime
import functools
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from bing_webmaster_mcp.skills import skill_read as _skill_read, skills_list as _skills_list
from bing_webmaster_mcp.telemetry import (
    MCP_SERVER_VERSION,
    announce_and_fire_boot_events,
    track_event,
    track_tool_call,
)

BING_API_BASE = "https://ssl.bing.com/webmaster/api.svc/json"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

# ---------------------------------------------------------------------------
# Universal fleet update checker (async, non-blocking, 24h TTL, 7d re-nudge)
# ---------------------------------------------------------------------------
_FLEET_CACHE_FILE = Path.home() / ".cache" / "mcp_fleet_updates.json"
_UPDATE_CHECK_TTL = 86400
_NUDGE_THROTTLE_INTERVAL = 7 * 86400


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        clean = re.sub(r"[^\d.]", "", v)
        return tuple(int(p) for p in clean.split(".") if p.isdigit())
    except Exception:
        return (0,)


def check_server_update(package_name: str, current_version: str, force_check: bool = False) -> dict:
    now = time.time()
    cache: dict[str, Any] = {}
    if _FLEET_CACHE_FILE.exists():
        try:
            cache = json.loads(_FLEET_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    entry = cache.get(package_name, {})
    last_check = entry.get("last_checked", 0)
    latest_version = entry.get("latest_version", current_version)

    if force_check or (now - last_check > _UPDATE_CHECK_TTL):
        try:
            req = urllib.request.Request(
                f"https://pypi.org/pypi/{package_name}/json",
                headers={"User-Agent": f"{package_name}/{current_version}"},
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                latest_version = data.get("info", {}).get("version", current_version)
                entry["latest_version"] = latest_version
                entry["last_checked"] = now
                cache[package_name] = entry
                _FLEET_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                tmp = _FLEET_CACHE_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(cache), encoding="utf-8")
                tmp.replace(_FLEET_CACHE_FILE)
        except Exception:
            pass

    has_update = _parse_version(latest_version) > _parse_version(current_version)
    cmd = f"uvx --refresh {package_name}"
    msg = (
        f"An updated version of {package_name} is available (v{latest_version}, current: v{current_version}). "
        f"Inform the user to run '{cmd}' to update. Do NOT attempt to run this command yourself in this session."
        if has_update
        else f"{package_name} is up to date (v{current_version})."
    )
    return {
        "server": package_name,
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": has_update,
        "upgrade_command": cmd if has_update else None,
        "message": msg,
    }


def get_upgrade_nudge(package_name: str, current_version: str) -> str:
    try:
        now = time.time()
        cache: dict[str, Any] = {}
        if _FLEET_CACHE_FILE.exists():
            try:
                cache = json.loads(_FLEET_CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

        entry = cache.get(package_name, {})
        last_check = entry.get("last_checked", 0)
        latest_version = entry.get("latest_version", current_version)
        last_nudged = entry.get("last_nudged", 0)

        if now - last_check > _UPDATE_CHECK_TTL:
            def _fetch():
                try:
                    req = urllib.request.Request(
                        f"https://pypi.org/pypi/{package_name}/json",
                        headers={"User-Agent": f"{package_name}/{current_version}"},
                    )
                    with urllib.request.urlopen(req, timeout=1.5) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        latest = data.get("info", {}).get("version", current_version)
                        _FLEET_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                        cur = json.loads(_FLEET_CACHE_FILE.read_text(encoding="utf-8")) if _FLEET_CACHE_FILE.exists() else {}
                        cur[package_name] = {
                            "latest_version": latest,
                            "last_checked": time.time(),
                            "last_nudged": cur.get(package_name, {}).get("last_nudged", 0),
                        }
                        tmp = _FLEET_CACHE_FILE.with_suffix(".tmp")
                        tmp.write_text(json.dumps(cur), encoding="utf-8")
                        tmp.replace(_FLEET_CACHE_FILE)
                except Exception:
                    pass

            threading.Thread(target=_fetch, daemon=True).start()

        if _parse_version(latest_version) > _parse_version(current_version):
            if now - last_nudged > _NUDGE_THROTTLE_INTERVAL:
                entry["last_nudged"] = now
                entry["latest_version"] = latest_version
                entry["last_checked"] = last_check
                cache[package_name] = entry
                try:
                    _FLEET_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                    _FLEET_CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
                except Exception:
                    pass
                return (
                    f"\n\n[NOTICE: An updated version of {package_name} is available (v{latest_version}, current: v{current_version}). "
                    f"Inform the user to run 'uvx --refresh {package_name}' to update. Do NOT attempt to run this command yourself in this session.]"
                )
    except Exception:
        pass
    return ""


def _append_upgrade_nudge(out_str: str) -> str:
    nudge = get_upgrade_nudge("bing-webmaster-mcp", MCP_SERVER_VERSION)
    if not nudge:
        return out_str
    try:
        data = json.loads(out_str)
        if isinstance(data, dict):
            data["_upgrade_notice"] = nudge.strip()
            return json.dumps(data, indent=2)
    except Exception:
        pass
    return out_str + nudge


# ---------------------------------------------------------------------------
# FastMCP Server Initialization
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "bing-webmaster-mcp",
    title="Bing Webmaster Tools & IndexNow MCP Server",
    version=MCP_SERVER_VERSION,
    website_url="https://bing-webmaster.builditwithai.xyz",
)

_orig_tool = mcp.tool


def _upgrade_tool(*args, **kwargs):
    def dec(fn):
        @functools.wraps(fn)
        def wrapper(*f_args, **f_kwargs):
            res = fn(*f_args, **f_kwargs)
            if isinstance(res, str):
                return _append_upgrade_nudge(res)
            return res

        return _orig_tool(*args, **kwargs)(wrapper)

    return dec


mcp.tool = _upgrade_tool


# ---------------------------------------------------------------------------
# Helpers for Auth, URLs, Dates & HTTP Requests
# ---------------------------------------------------------------------------
def _resolve_bing_api_key(apikey: Optional[str] = None) -> Optional[str]:
    if apikey and apikey.strip():
        return apikey.strip()
    return os.getenv("BING_WEBMASTER_API_KEY") or os.getenv("BING_API_KEY")


def _resolve_indexnow_key(indexnow_key: Optional[str] = None, apikey: Optional[str] = None) -> Optional[str]:
    if indexnow_key and indexnow_key.strip():
        return indexnow_key.strip()
    key = os.getenv("INDEXNOW_KEY") or os.getenv("INDEX_NOW_KEY")
    if key and key.strip():
        return key.strip()
    if apikey and apikey.strip():
        return apikey.strip()
    return None


def _format_missing_key_error() -> str:
    return (
        "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN] Missing Bing Webmaster API key.\n\n"
        "To generate your API Key:\n"
        "1. Sign in to Bing Webmaster Tools: https://www.bing.com/webmasters\n"
        "2. Click the Settings icon (gear in top right) -> API Access -> API Key.\n"
        "3. Click 'Generate API Key' (or copy your existing key).\n"
        "4. Provide it via the `apikey` parameter in tool calls, or export it in your environment: `export BING_WEBMASTER_API_KEY=\"<your_key>\"`."
    )


def _format_http_error(err: urllib.error.HTTPError, site_url: Optional[str] = None) -> str:
    code = err.code
    reason = err.reason
    try:
        body = err.read().decode("utf-8", "replace")
    except Exception:
        body = ""

    if code in (401, 403):
        return (
            f"[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN] Bing Webmaster API authentication failed (HTTP {code} {reason}).\n"
            "Your API key is invalid or unauthorized. Please verify the key at https://www.bing.com/webmasters "
            "(Settings -> API Access -> API Key)."
        )
    elif code == 400:
        if site_url and "not found" in body.lower():
            return (
                f"[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN] Site '{site_url}' is not registered or verified in this Bing Webmaster account.\n"
                "Call get_user_sites to see your verified properties, or add and verify the site at https://www.bing.com/webmasters."
            )
        return f"[INPUT_FIXABLE] Bad request to Bing Webmaster API (HTTP 400): {body or reason}. Verify site URL and parameter values."
    elif code == 404:
        return f"[INPUT_FIXABLE] Requested resource or site not found on Bing Webmaster API (HTTP 404): {body or reason}."
    elif code == 429:
        return f"[TRANSIENT] Bing Webmaster API rate limit exceeded (HTTP 429). Please wait a moment and retry."
    elif code >= 500:
        return f"[TRANSIENT] Bing Webmaster API server error (HTTP {code} {reason}). Upstream service temporarily unavailable; please retry."
    return f"[TRANSIENT] HTTP error from Bing Webmaster API (HTTP {code} {reason}): {body[:300]}."


def _parse_bing_date(val: Any) -> str:
    if not val:
        return ""
    if isinstance(val, str):
        m = re.search(r"/Date\((\d+)(?:[+-]\d+)?\)/", val)
        if m:
            try:
                ms = int(m.group(1))
                dt = datetime.datetime.fromtimestamp(ms / 1000.0, tz=datetime.timezone.utc)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
    return str(val)


def _clean_position(val: Any) -> float:
    try:
        f = float(val)
        if f > 10.0:
            return round(f / 10.0, 1)
        return round(f, 1)
    except (ValueError, TypeError):
        return 0.0


def _validate_site_url(site_url: str) -> Optional[str]:
    if not site_url or not isinstance(site_url, str) or not site_url.strip():
        return "[INPUT_FIXABLE] Empty site_url provided. Please provide a valid site URL, e.g. 'https://example.com'."
    parsed = urllib.parse.urlparse(site_url.strip())
    if not parsed.scheme or not parsed.netloc:
        return (
            f"[INPUT_FIXABLE] Invalid site_url '{site_url}'. "
            "Must be an absolute URL including protocol, e.g. 'https://example.com' or 'https://example.com/'."
        )
    return None


def _http_get_json(url: str, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": f"bing-webmaster-mcp/{MCP_SERVER_VERSION}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content = resp.read().decode("utf-8")
        return json.loads(content)


def _http_post_json(url: str, payload: dict, timeout: float = 10.0) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": f"bing-webmaster-mcp/{MCP_SERVER_VERSION}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Tool Implementations
# ---------------------------------------------------------------------------
@mcp.tool()
def get_user_sites(apikey: Optional[str] = None) -> str:
    """Retrieve all sites associated with the authenticated Bing Webmaster Tools account.

    Returns the list of verified and unverified properties, authentication codes,
    and DNS verification records.
    """
    t0 = time.perf_counter()
    key = _resolve_bing_api_key(apikey)
    if not key:
        err = _format_missing_key_error()
        track_tool_call("get_user_sites", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="AuthError", error_message=err)
        return err

    url = f"{BING_API_BASE}/GetUserSites?apikey={urllib.parse.quote(key)}"
    try:
        data = _http_get_json(url)
        raw_sites = data.get("d", []) if isinstance(data, dict) else []
        sites = []
        for s in raw_sites:
            sites.append({
                "url": s.get("Url"),
                "is_verified": s.get("IsVerified", False),
                "auth_code": s.get("AuthenticationCode"),
                "dns_verification_code": s.get("DnsVerificationCode"),
            })
        result = {
            "total_sites": len(sites),
            "verified_count": sum(1 for s in sites if s.get("is_verified")),
            "sites": sites,
        }
        out = json.dumps(result, indent=2)
        track_tool_call("get_user_sites", (time.perf_counter() - t0) * 1000, "success", len(sites), len(out))
        return out
    except urllib.error.HTTPError as e:
        err = _format_http_error(e)
        track_tool_call("get_user_sites", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="HTTPError", error_message=err)
        return err
    except urllib.error.URLError as e:
        err = f"[TRANSIENT] Network connectivity failure connecting to Bing Webmaster API: {e.reason}. Please retry."
        track_tool_call("get_user_sites", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="NetworkError", error_message=err)
        return err
    except Exception as e:
        err = f"[TRANSIENT] Unexpected error calling get_user_sites ({type(e).__name__}: {str(e)}). Please retry."
        track_tool_call("get_user_sites", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat=type(e).__name__, error_message=err)
        return err


@mcp.tool()
def get_query_stats(site_url: str, apikey: Optional[str] = None) -> str:
    """Get search query performance metrics (clicks, impressions, CTR, average position) for a verified site.

    Aggregates query-level totals and calculates overall metrics on the server.
    """
    t0 = time.perf_counter()
    url_err = _validate_site_url(site_url)
    if url_err:
        track_tool_call("get_query_stats", (time.perf_counter() - t0) * 1000, "error", 0, len(url_err), cat="ValidationError", error_message=url_err)
        return url_err

    key = _resolve_bing_api_key(apikey)
    if not key:
        err = _format_missing_key_error()
        track_tool_call("get_query_stats", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="AuthError", error_message=err)
        return err

    clean_site = site_url.strip()
    api_url = f"{BING_API_BASE}/GetQueryStats?siteUrl={urllib.parse.quote(clean_site)}&apikey={urllib.parse.quote(key)}"
    try:
        data = _http_get_json(api_url)
        raw_rows = data.get("d", []) if isinstance(data, dict) else []
        queries = []
        for r in raw_rows:
            clicks = int(r.get("Clicks", 0))
            impressions = int(r.get("Impressions", 0))
            ctr = round((clicks / impressions * 100.0), 2) if impressions > 0 else 0.0
            queries.append({
                "query": r.get("Query", ""),
                "clicks": clicks,
                "impressions": impressions,
                "ctr_percent": ctr,
                "avg_click_position": _clean_position(r.get("AvgClickPosition", 0)),
                "avg_impression_position": _clean_position(r.get("AvgImpressionPosition", 0)),
                "date": _parse_bing_date(r.get("Date")),
            })

        total_clicks = sum(q["clicks"] for q in queries)
        total_impressions = sum(q["impressions"] for q in queries)
        overall_ctr = round((total_clicks / total_impressions * 100.0), 2) if total_impressions > 0 else 0.0
        weighted_pos = (
            round(sum(q["avg_click_position"] * q["clicks"] for q in queries) / total_clicks, 1)
            if total_clicks > 0
            else 0.0
        )

        result = {
            "site_url": clean_site,
            "summary": {
                "total_queries": len(queries),
                "total_clicks": total_clicks,
                "total_impressions": total_impressions,
                "overall_ctr_percent": overall_ctr,
                "overall_avg_click_position": weighted_pos,
            },
            "queries": queries,
        }
        out = json.dumps(result, indent=2)
        track_tool_call("get_query_stats", (time.perf_counter() - t0) * 1000, "success", len(queries), len(out))
        return out
    except urllib.error.HTTPError as e:
        err = _format_http_error(e, clean_site)
        track_tool_call("get_query_stats", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="HTTPError", error_message=err)
        return err
    except urllib.error.URLError as e:
        err = f"[TRANSIENT] Network error connecting to Bing Webmaster API: {e.reason}. Please retry."
        track_tool_call("get_query_stats", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="NetworkError", error_message=err)
        return err
    except Exception as e:
        err = f"[TRANSIENT] Error executing get_query_stats ({type(e).__name__}: {str(e)}). Please retry."
        track_tool_call("get_query_stats", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat=type(e).__name__, error_message=err)
        return err


@mcp.tool()
def get_page_stats(site_url: str, apikey: Optional[str] = None) -> str:
    """Get page-level traffic and performance metrics for URLs on a verified site.

    Exposes URL-level clicks, impressions, CTR, positions, and aggregate site totals.
    """
    t0 = time.perf_counter()
    url_err = _validate_site_url(site_url)
    if url_err:
        track_tool_call("get_page_stats", (time.perf_counter() - t0) * 1000, "error", 0, len(url_err), cat="ValidationError", error_message=url_err)
        return url_err

    key = _resolve_bing_api_key(apikey)
    if not key:
        err = _format_missing_key_error()
        track_tool_call("get_page_stats", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="AuthError", error_message=err)
        return err

    clean_site = site_url.strip()
    api_url = f"{BING_API_BASE}/GetPageStats?siteUrl={urllib.parse.quote(clean_site)}&apikey={urllib.parse.quote(key)}"
    try:
        data = _http_get_json(api_url)
        raw_rows = data.get("d", []) if isinstance(data, dict) else []
        pages = []
        for r in raw_rows:
            clicks = int(r.get("Clicks", 0))
            impressions = int(r.get("Impressions", 0))
            ctr = round((clicks / impressions * 100.0), 2) if impressions > 0 else 0.0
            page_url = r.get("Query", "")  # Bing returns page URL in the Query field
            pages.append({
                "page_url": page_url,
                "clicks": clicks,
                "impressions": impressions,
                "ctr_percent": ctr,
                "avg_click_position": _clean_position(r.get("AvgClickPosition", 0)),
                "avg_impression_position": _clean_position(r.get("AvgImpressionPosition", 0)),
                "date": _parse_bing_date(r.get("Date")),
            })

        total_clicks = sum(p["clicks"] for p in pages)
        total_impressions = sum(p["impressions"] for p in pages)
        overall_ctr = round((total_clicks / total_impressions * 100.0), 2) if total_impressions > 0 else 0.0

        result = {
            "site_url": clean_site,
            "summary": {
                "total_pages": len(pages),
                "total_clicks": total_clicks,
                "total_impressions": total_impressions,
                "overall_ctr_percent": overall_ctr,
            },
            "pages": pages,
        }
        out = json.dumps(result, indent=2)
        track_tool_call("get_page_stats", (time.perf_counter() - t0) * 1000, "success", len(pages), len(out))
        return out
    except urllib.error.HTTPError as e:
        err = _format_http_error(e, clean_site)
        track_tool_call("get_page_stats", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="HTTPError", error_message=err)
        return err
    except urllib.error.URLError as e:
        err = f"[TRANSIENT] Network error connecting to Bing Webmaster API: {e.reason}. Please retry."
        track_tool_call("get_page_stats", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="NetworkError", error_message=err)
        return err
    except Exception as e:
        err = f"[TRANSIENT] Error executing get_page_stats ({type(e).__name__}: {str(e)}). Please retry."
        track_tool_call("get_page_stats", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat=type(e).__name__, error_message=err)
        return err


@mcp.tool()
def get_crawl_issues(site_url: str, apikey: Optional[str] = None) -> str:
    """Retrieve crawl errors, HTTP status diagnostics, and link graph issues reported by Bingbot.

    Groups crawl blockers by HTTP status code and in-link severity.
    """
    t0 = time.perf_counter()
    url_err = _validate_site_url(site_url)
    if url_err:
        track_tool_call("get_crawl_issues", (time.perf_counter() - t0) * 1000, "error", 0, len(url_err), cat="ValidationError", error_message=url_err)
        return url_err

    key = _resolve_bing_api_key(apikey)
    if not key:
        err = _format_missing_key_error()
        track_tool_call("get_crawl_issues", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="AuthError", error_message=err)
        return err

    clean_site = site_url.strip()
    api_url = f"{BING_API_BASE}/GetCrawlIssues?siteUrl={urllib.parse.quote(clean_site)}&apikey={urllib.parse.quote(key)}"
    try:
        data = _http_get_json(api_url)
        raw_issues = data.get("d", []) if isinstance(data, dict) else []
        issues = []
        code_counts: dict[str, int] = {}
        for r in raw_issues:
            code = str(r.get("HttpCode", "Unknown"))
            code_counts[code] = code_counts.get(code, 0) + 1
            issues.append({
                "url": r.get("Url"),
                "http_code": code,
                "issue_type": r.get("Issues", ""),
                "in_links": int(r.get("InLinks", 0)) if r.get("InLinks") is not None else 0,
            })

        result = {
            "site_url": clean_site,
            "summary": {
                "total_issues": len(issues),
                "by_http_code": code_counts,
            },
            "issues": issues,
        }
        out = json.dumps(result, indent=2)
        track_tool_call("get_crawl_issues", (time.perf_counter() - t0) * 1000, "success", len(issues), len(out))
        return out
    except urllib.error.HTTPError as e:
        err = _format_http_error(e, clean_site)
        track_tool_call("get_crawl_issues", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="HTTPError", error_message=err)
        return err
    except urllib.error.URLError as e:
        err = f"[TRANSIENT] Network error connecting to Bing Webmaster API: {e.reason}. Please retry."
        track_tool_call("get_crawl_issues", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="NetworkError", error_message=err)
        return err
    except Exception as e:
        err = f"[TRANSIENT] Error executing get_crawl_issues ({type(e).__name__}: {str(e)}). Please retry."
        track_tool_call("get_crawl_issues", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat=type(e).__name__, error_message=err)
        return err


@mcp.tool()
def submit_urls(
    site_url: str,
    urls: List[str],
    apikey: Optional[str] = None,
    indexnow_key: Optional[str] = None,
) -> str:
    """Submit a batch of URLs for rapid crawling and indexing via Bing Webmaster API and IndexNow protocol.

    Dual-submission:
    1. Bing Webmaster Tools API SubmitUrlbatch endpoint.
    2. IndexNow open protocol (https://api.indexnow.org/indexnow).
    """
    t0 = time.perf_counter()
    url_err = _validate_site_url(site_url)
    if url_err:
        track_tool_call("submit_urls", (time.perf_counter() - t0) * 1000, "error", 0, len(url_err), cat="ValidationError", error_message=url_err)
        return url_err

    if not urls or not isinstance(urls, list) or len(urls) == 0:
        err = "[INPUT_FIXABLE] No URLs provided in `urls`. Please supply a non-empty list of URLs to submit."
        track_tool_call("submit_urls", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="ValidationError", error_message=err)
        return err

    clean_site = site_url.strip()
    site_parsed = urllib.parse.urlparse(clean_site)
    site_host = site_parsed.netloc.lower()

    # Validate individual URLs
    clean_urls: list[str] = []
    for u in urls:
        if not isinstance(u, str) or not u.strip():
            continue
        cu = u.strip()
        p = urllib.parse.urlparse(cu)
        if not p.scheme or not p.netloc:
            err = f"[INPUT_FIXABLE] Invalid URL '{cu}'. URLs must be absolute (e.g. 'https://{site_host}/path')."
            track_tool_call("submit_urls", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="ValidationError", error_message=err)
            return err
        if p.netloc.lower() != site_host and not p.netloc.lower().endswith("." + site_host):
            err = (
                f"[INPUT_FIXABLE] Host mismatch: URL '{cu}' belongs to '{p.netloc}', "
                f"which does not match site_url host '{site_host}'."
            )
            track_tool_call("submit_urls", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="ValidationError", error_message=err)
            return err
        clean_urls.append(cu)

    if not clean_urls:
        err = "[INPUT_FIXABLE] All provided URLs were empty or invalid."
        track_tool_call("submit_urls", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="ValidationError", error_message=err)
        return err

    bing_key = _resolve_bing_api_key(apikey)
    idx_key = _resolve_indexnow_key(indexnow_key, apikey)

    if not bing_key and not idx_key:
        err = (
            "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN] Neither Bing Webmaster API key nor IndexNow key provided.\n\n"
            "To submit URLs, provide at least one key:\n"
            "1. Bing Webmaster API Key: Set `BING_WEBMASTER_API_KEY` or pass `apikey`.\n"
            "   (Get it at https://www.bing.com/webmasters -> Settings -> API Access -> API Key)\n"
            "2. IndexNow Key: Set `INDEXNOW_KEY` or pass `indexnow_key`.\n"
            "   (Generate an 8-128 hex string and host it at https://<domain>/<key>.txt)"
        )
        track_tool_call("submit_urls", (time.perf_counter() - t0) * 1000, "error", 0, len(err), cat="AuthError", error_message=err)
        return err

    submission_results: dict[str, Any] = {
        "site_url": clean_site,
        "submitted_count": len(clean_urls),
        "urls": clean_urls,
        "protocols": {},
    }

    # 1. Bing Webmaster API SubmitUrlbatch
    if bing_key:
        api_url = f"{BING_API_BASE}/SubmitUrlbatch?apikey={urllib.parse.quote(bing_key)}"
        payload = {"siteUrl": clean_site, "urlList": clean_urls}
        try:
            status, resp_body = _http_post_json(api_url, payload)
            if status in (200, 204):
                submission_results["protocols"]["bing_webmaster_api"] = {
                    "status": "success",
                    "code": status,
                    "message": "Batch submitted successfully to Bing Webmaster Tools API.",
                }
            else:
                submission_results["protocols"]["bing_webmaster_api"] = {
                    "status": "error",
                    "code": status,
                    "message": resp_body[:200],
                }
        except urllib.error.HTTPError as e:
            submission_results["protocols"]["bing_webmaster_api"] = {
                "status": "error",
                "code": e.code,
                "message": _format_http_error(e, clean_site),
            }
        except Exception as e:
            submission_results["protocols"]["bing_webmaster_api"] = {
                "status": "error",
                "code": 0,
                "message": f"Connection error ({type(e).__name__}): {str(e)}",
            }
    else:
        submission_results["protocols"]["bing_webmaster_api"] = {
            "status": "skipped",
            "message": "No Bing Webmaster API key provided.",
        }

    # 2. IndexNow Open Protocol
    if idx_key:
        idx_payload = {
            "host": site_host,
            "key": idx_key,
            "urlList": clean_urls,
        }
        try:
            status, resp_body = _http_post_json(INDEXNOW_ENDPOINT, idx_payload)
            if status == 200:
                msg = "URLs submitted successfully to IndexNow."
            elif status == 202:
                msg = "URLs submitted successfully to IndexNow (key pending validation)."
            elif status == 400:
                msg = "[INPUT_FIXABLE] Invalid request format for IndexNow."
            elif status == 403:
                msg = "[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN] IndexNow key invalid or not found on host."
            elif status == 422:
                msg = "[INPUT_FIXABLE] URLs do not belong to the host."
            elif status == 429:
                msg = "[TRANSIENT] IndexNow rate limit reached (too many requests)."
            else:
                msg = f"IndexNow returned HTTP {status}: {resp_body[:200]}"

            submission_results["protocols"]["indexnow"] = {
                "status": "success" if status in (200, 202) else "error",
                "code": status,
                "message": msg,
            }
        except urllib.error.HTTPError as e:
            submission_results["protocols"]["indexnow"] = {
                "status": "error",
                "code": e.code,
                "message": f"IndexNow HTTP {e.code}: {e.reason}",
            }
        except Exception as e:
            submission_results["protocols"]["indexnow"] = {
                "status": "error",
                "code": 0,
                "message": f"IndexNow connection error ({type(e).__name__}): {str(e)}",
            }
    else:
        submission_results["protocols"]["indexnow"] = {
            "status": "skipped",
            "message": "No IndexNow key provided.",
        }

    out = json.dumps(submission_results, indent=2)
    # Check if all attempted protocols failed
    attempted = [v for v in submission_results["protocols"].values() if v.get("status") != "skipped"]
    all_failed = attempted and all(v.get("status") == "error" for v in attempted)
    status_label = "error" if all_failed else "success"
    track_tool_call("submit_urls", (time.perf_counter() - t0) * 1000, status_label, len(clean_urls), len(out))
    return out


@mcp.tool()
def doctor() -> str:
    """Run diagnostics on Bing Webmaster API credentials, IndexNow configuration, telemetry, and test beds."""
    t0 = time.perf_counter()
    report: dict[str, Any] = {
        "server": "bing-webmaster-mcp",
        "version": MCP_SERVER_VERSION,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "diagnostics": {},
    }

    # 1. API Key Checks
    b_key = _resolve_bing_api_key()
    idx_key = _resolve_indexnow_key()

    report["diagnostics"]["bing_webmaster_api_key"] = {
        "status": "configured" if b_key else "missing",
        "masked": f"****{b_key[-4:]}" if b_key and len(b_key) >= 4 else ("present" if b_key else None),
        "source": "BING_WEBMASTER_API_KEY / BING_API_KEY",
    }
    report["diagnostics"]["indexnow_key"] = {
        "status": "configured" if idx_key else "missing",
        "masked": f"****{idx_key[-4:]}" if idx_key and len(idx_key) >= 4 else ("present" if idx_key else None),
        "source": "INDEXNOW_KEY",
    }

    # 2. Telemetry Opt-out Status
    dnt = os.getenv("DO_NOT_TRACK", "").lower() in ("1", "true")
    mcp_opt = os.getenv("MCP_TELEMETRY_OPT_OUT", "").lower() in ("1", "true")
    report["diagnostics"]["telemetry"] = {
        "opted_out": dnt or mcp_opt,
        "do_not_track": dnt,
        "mcp_telemetry_opt_out": mcp_opt,
    }

    # 3. Live Connectivity Probes
    connectivity: dict[str, Any] = {}
    if b_key:
        try:
            test_url = f"{BING_API_BASE}/GetUserSites?apikey={urllib.parse.quote(b_key)}"
            data = _http_get_json(test_url, timeout=5.0)
            sites = data.get("d", []) if isinstance(data, dict) else []
            connectivity["bing_webmaster_api"] = {
                "status": "connected",
                "verified_sites_count": len(sites),
            }
        except urllib.error.HTTPError as e:
            connectivity["bing_webmaster_api"] = {
                "status": "auth_failed",
                "code": e.code,
                "error": _format_http_error(e),
            }
        except Exception as e:
            connectivity["bing_webmaster_api"] = {
                "status": "unreachable",
                "error": str(e),
            }
    else:
        connectivity["bing_webmaster_api"] = {
            "status": "untested",
            "reason": "Missing BING_WEBMASTER_API_KEY",
        }

    # Probe IndexNow endpoint reachability
    try:
        req = urllib.request.Request(
            INDEXNOW_ENDPOINT,
            headers={"User-Agent": f"bing-webmaster-mcp/{MCP_SERVER_VERSION}"},
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            status_code = getattr(resp, "status", 200)
            if not isinstance(status_code, int):
                try:
                    status_code = int(status_code)
                except Exception:
                    status_code = 200
            connectivity["indexnow_endpoint"] = {"status": "reachable", "code": status_code}
    except urllib.error.HTTPError as e:
        # IndexNow GET returns 400 or 405 because it expects POST, which confirms server is live!
        connectivity["indexnow_endpoint"] = {"status": "reachable", "code": int(getattr(e, "code", 400))}
    except Exception as e:
        connectivity["indexnow_endpoint"] = {"status": "unreachable", "error": str(e)}

    report["diagnostics"]["connectivity"] = connectivity

    # 4. Fleet Test Beds Check
    test_beds = ["https://surendranb.com", "https://freeinference.dev", "https://builditwithai.xyz"]
    report["diagnostics"]["test_beds"] = {
        "configured_sample_domains": test_beds,
        "note": "Use these domains with get_query_stats, get_page_stats, and get_crawl_issues once verified.",
    }

    # 5. Actionable Guidance
    actionable = []
    if not b_key:
        actionable.append(
            "Configure Bing Webmaster API key: Generate at https://www.bing.com/webmasters (Settings -> API Access -> API Key) "
            "and set BING_WEBMASTER_API_KEY."
        )
    if not idx_key:
        actionable.append(
            "Configure IndexNow: Place an indexnow key file (e.g. <key>.txt) on your root web server and set INDEXNOW_KEY."
        )
    if not actionable:
        actionable.append("All core credentials and endpoints are healthy.")
    report["guidance"] = actionable

    out = json.dumps(report, indent=2)
    track_tool_call("doctor", (time.perf_counter() - t0) * 1000, "success", 1, len(out))
    return out


@mcp.tool()
def skills_list() -> str:
    """List available workflow playbooks and diagnostic guides for Bing Webmaster Tools."""
    return _skills_list()


@mcp.tool()
def skill_read(name: str) -> str:
    """Read a specific skill or playbook by name."""
    return _skill_read(name)


@mcp.tool()
def check_for_updates() -> str:
    """Check PyPI for newer versions of bing-webmaster-mcp and get upgrade instructions."""
    res = check_server_update("bing-webmaster-mcp", MCP_SERVER_VERSION, force_check=True)
    return json.dumps(res, indent=2)


def main():
    announce_and_fire_boot_events()
    track_event("mcp_started", {})
    mcp.run()


if __name__ == "__main__":
    main()
