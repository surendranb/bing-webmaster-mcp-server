# SPDX-License-Identifier: MIT
"""Dynamic skills loader for bing-webmaster-mcp.

Fetches up-to-date guidance, playbooks, and diagnostic strategies from GitHub at runtime
with automatic fallback to local repository skills.
"""
from __future__ import annotations
import json
import time
import urllib.request
from pathlib import Path
from typing import Optional
from bing_webmaster_mcp.telemetry import track_event, track_tool_call

SKILLS_URL = "https://raw.githubusercontent.com/surendranb/bing-webmaster-mcp-server/main/skills"
BUILTIN_SKILLS = ["bing-webmaster-audit", "indexnow-instant-indexing", "bing_setup"]


def _get_local_skills_dir() -> Path:
    # Check parent hierarchy (src/bing_webmaster_mcp -> repo root / skills)
    cand = Path(__file__).resolve().parent.parent.parent / "skills"
    if cand.is_dir():
        return cand
    # Fallback to adjacent skills folder
    cand2 = Path(__file__).resolve().parent / "skills"
    return cand2


def list_available_skills() -> list[str]:
    found: set[str] = set(BUILTIN_SKILLS)
    local_dir = _get_local_skills_dir()
    if local_dir.is_dir():
        for p in local_dir.glob("*.md"):
            found.add(p.stem)
    return sorted(found)


def skills_list() -> str:
    """List available skills (dynamic, GitHub-first with local fallback)."""
    t0 = time.perf_counter()
    names = list_available_skills()
    out = json.dumps({"skills": names, "source": "github+local"}, indent=2)
    track_tool_call("skills_list", (time.perf_counter() - t0) * 1000, "success", len(names), len(out))
    return out


def _normalize_skill_name(name: str) -> str:
    s = name.strip()
    if s.endswith(".md"):
        s = s[:-3]
    if s in ("setup", "bing-setup", "bing_setup"):
        return "bing_setup"
    return "".join(c for c in s if c.isalnum() or c in ("_", "-"))


def skill_read(name: str) -> str:
    """Fetch SKILL.md by name from GitHub, with local fallback and error absorption."""
    t0 = time.perf_counter()
    safe = _normalize_skill_name(name)
    if not safe:
        avail = ", ".join(list_available_skills())
        out = f"[INPUT_FIXABLE] Empty skill name provided. Available skills: {avail}. Call skills_list to view all available skills."
        track_tool_call("skill_read", (time.perf_counter() - t0) * 1000, "error", 0, len(out), cat="ValidationError", msg=out)
        return out

    # Candidates to try: safe, and variant with hyphen/underscore swapped
    candidates = [safe]
    alt = safe.replace("_", "-") if "_" in safe else safe.replace("-", "_")
    if alt not in candidates:
        candidates.append(alt)

    # 1. Try remote GitHub fetch
    for cand in candidates:
        try:
            url = f"{SKILLS_URL}/{cand}.md"
            req = urllib.request.Request(url, headers={"User-Agent": "bing-webmaster-mcp-skills"})
            with urllib.request.urlopen(req, timeout=4.0) as r:
                text = r.read().decode("utf-8", "replace")
                track_tool_call("skill_read", (time.perf_counter() - t0) * 1000, "success", 1, len(text))
                return text
        except Exception:
            pass

    # 2. Local fallback (repo root / dev clone)
    local_dir = _get_local_skills_dir()
    for cand in candidates:
        local_file = local_dir / f"{cand}.md"
        if local_file.is_file():
            text = local_file.read_text(encoding="utf-8")
            track_tool_call("skill_read", (time.perf_counter() - t0) * 1000, "success", 1, len(text))
            return text

    # 3. Not found - error absorption with candidates
    avail = ", ".join(list_available_skills())
    out = (
        f"[INPUT_FIXABLE] Unknown skill '{name}'. Available skills: {avail}. "
        f"If network is blocked: [TRANSIENT] retry, or [ENVIRONMENT_FIXABLE: STOP & ASK HUMAN] if GitHub raw content is blocked by network proxy."
    )
    track_tool_call("skill_read", (time.perf_counter() - t0) * 1000, "error", 0, len(out), cat="NotFoundError", msg=out)
    return out
