# Bing Webmaster Tools & IndexNow MCP Server

High-signal Model Context Protocol (MCP) server for Microsoft Bing Webmaster Tools and IndexNow instant search engine indexing.

[![PyPI version](https://img.shields.io/pypi/v/bing-webmaster-mcp.svg)](https://pypi.org/project/bing-webmaster-mcp/)
[![npm version](https://img.shields.io/npm/v/bing-webmaster-tools-mcp.svg)](https://www.npmjs.com/package/bing-webmaster-tools-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Companion to [`google-search-console-mcp`](https://github.com/surendranb/google-search-console-mcp) for agentic SEO, search analytics, and automated indexing pipelines.

---

## Capabilities & Tools

1. **`get_user_sites(apikey?)`**: List all verified and unverified domains, authentication codes, and DNS verification records.
2. **`get_query_stats(site_url, apikey?)`**: Retrieve search performance metrics (clicks, impressions, CTR %, average click and impression positions) broken down by query, with aggregated totals calculated server-side.
3. **`get_page_stats(site_url, apikey?)`**: Fetch URL-level traffic and performance metrics for top pages.
4. **`get_crawl_issues(site_url, apikey?)`**: Inspect crawl errors, HTTP status diagnostics (404s, 500s), and in-link severity encountered by Bingbot.
5. **`submit_urls(site_url, urls, apikey?, indexnow_key?)`**: Dual-submit URLs for immediate indexing via both the Bing Webmaster API and the IndexNow open protocol (`https://api.indexnow.org/indexnow`).
6. **`doctor()`**: Run diagnostics on API credentials, IndexNow key setup, telemetry opt-out status, and test beds.
7. **`skills_list()` / `skill_read(name)`**: Access dynamic workflow playbooks (e.g. `bing-webmaster-audit`, `indexnow-instant-indexing`) loaded from GitHub.
8. **`check_for_updates()`**: Verify against PyPI for newer releases.

---

## Installation

### Python (`uvx` - Recommended)

```bash
uvx bing-webmaster-mcp
```

### Node / npm (`npx`)

```bash
npx bing-webmaster-tools-mcp
```

---

## Configuration

Set the environment variables in your MCP client configuration:

- `BING_WEBMASTER_API_KEY`: Your Bing Webmaster Tools API key.
- `INDEXNOW_KEY` (Optional): Your IndexNow API key for instant multi-engine indexing.

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bing-webmaster": {
      "command": "uvx",
      "args": ["bing-webmaster-mcp"],
      "env": {
        "BING_WEBMASTER_API_KEY": "YOUR_BING_API_KEY",
        "INDEXNOW_KEY": "YOUR_INDEXNOW_KEY"
      }
    }
  }
}
```

Or via npx:

```json
{
  "mcpServers": {
    "bing-webmaster": {
      "command": "npx",
      "args": ["-y", "bing-webmaster-tools-mcp"],
      "env": {
        "BING_WEBMASTER_API_KEY": "YOUR_BING_API_KEY"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "bing-webmaster": {
      "command": "uvx",
      "args": ["bing-webmaster-mcp"],
      "env": {
        "BING_WEBMASTER_API_KEY": "YOUR_BING_API_KEY"
      }
    }
  }
}
```

---

## How to Get Credentials

### Bing Webmaster Tools API Key
1. Sign in to [Bing Webmaster Tools](https://www.bing.com/webmasters).
2. Click the **Settings** gear icon in the top right corner.
3. Select **API Access** > **API Key**.
4. Click **Generate API Key** (or copy existing key).

### IndexNow Key
1. Generate an 8-128 character hex key or UUID.
2. Host a text file named `<your-key>.txt` containing only the key at your website root (e.g., `https://example.com/<your-key>.txt`).
3. Set `INDEXNOW_KEY="<your-key>"`.

---

## Error Handling & Model UX

Every error message is classified so AI agents know whether to ask for human help or self-correct:
- `[INPUT_FIXABLE]`: Malformed URLs, host mismatches, or missing arguments. Correctable by the model.
- `[ENVIRONMENT_FIXABLE: STOP & ASK HUMAN]`: Missing or unauthorized API keys, or unverified sites. Stop and request human intervention.
- `[TRANSIENT]`: Rate limits (HTTP 429) or upstream downtime. Safe to retry after a pause.

---

## Telemetry & Privacy

This server includes anonymous usage telemetry to monitor tool performance and errors.
To opt out completely, set either:
```bash
export DO_NOT_TRACK=1
# or
export MCP_TELEMETRY_OPT_OUT=1
```
API keys, URLs, and sensitive arguments are strictly redacted before transmission.

---

## License

MIT © [Surendran B](https://github.com/surendranb)
