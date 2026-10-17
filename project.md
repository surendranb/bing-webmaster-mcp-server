# Project: bing-webmaster-mcp-server
**Description:** High-signal Model Context Protocol (MCP) server for Bing Webmaster Tools & IndexNow API.

## Context
- **Pillar:** Professional
- **Domain:** Business -> Marketing -> SEO
- **Strategic Intent:** Search performance, query analytics, crawl diagnostics, and instant search indexing via Bing Webmaster API & IndexNow.
- **Rules of Engagement:** Fleet v2 Standard (`~/Projects/mcp-playbook/MCP-BUILD-PLAYBOOK.md`)

## Active Intent
- Implementing Fleet v2 architecture for Ticket SUR-419 (`reachsuren/sur-419-build-and-publish-bing-webmaster-mcp-bing-webmaster-tools`).

## Roadmap
- [x] Initialize repository.
- [x] Implement FastMCP server with 6 core tools: `get_user_sites`, `get_query_stats`, `get_page_stats`, `get_crawl_issues`, `submit_urls` (Bing API + IndexNow), `doctor`.
- [x] Error Absorption Standard (`[INPUT_FIXABLE]`, `[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN]`, `[TRANSIENT]`).
- [x] Telemetry Schema v2 with dual-endpoint fallback (`https://bing-webmaster.builditwithai.xyz/e` and workers.dev) and opt-out support.
- [x] Dynamic GitHub skills layer (`skills_list`, `skill_read`) with local fallback and playbooks.
- [x] Dual-registry npm bridge (`bing-webmaster-tools-mcp`).
- [x] Deterministic test beds (`surendranb.com`, `freeinference.dev`, `builditwithai.xyz`) and native MCP stdio JSON-RPC test.
- [ ] Build distribution artifacts via `uv build`.
- [ ] Publish to PyPI and npm.

## Handover
- **Last Agent Actions:** Implemented full FastMCP server, telemetry v2, skills layer, npm wrapper, and test suites.
- **Next Steps:** Run pytest, native MCP protocol tests, and `uv build`.
- **Status:** In Progress (SUR-419)
- **Last Update:** 2026-10-17
