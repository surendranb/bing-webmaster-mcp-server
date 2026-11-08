---
title: Bing Webmaster Tools & IndexNow Setup Guide
description: Step-by-step instructions for human operators and AI agents to configure Bing Webmaster API keys, IndexNow verification, and MCP client harnesses.
version: 1.0.0
---

# Bing Webmaster Tools & IndexNow MCP Setup Guide

Use this playbook whenever you encounter an unconfigured Bing Webmaster environment, `401 Unauthorized`, `Invalid API Key`, or need to configure IndexNow instant indexing.

---

## 1. Quick Diagnostic Check

Run `get_user_sites()` first:
- **Returns list of sites**: Authentication is active. Note your site URL format (e.g. `https://example.com`).
- **401 Unauthorized / Missing API Key**: Follow Section 2 below to generate your Bing Webmaster API key.
- **Site not found**: Verify the site is added and verified in Bing Webmaster Tools console.

---

## 2. Generate Bing Webmaster Tools API Key

Bing Webmaster Tools uses a personal account API key that grants access to all sites verified under your account.

1. Open the [Bing Webmaster API Management](https://www.bing.com/webmasters/configure/apimanagement/apikey) console.
2. Sign in with your Microsoft / Bing Webmaster account.
3. Click **Generate API Key** (or copy your existing key).
4. Store this key securely (e.g. in your password manager or environment configuration).

---

## 3. Configure Client Harness Environment

Set the environment variable `BING_WEBMASTER_API_KEY` in your MCP client harness.

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "bing-webmaster": {
      "command": "uvx",
      "args": ["--from", "bing-webmaster-mcp", "bing-webmaster-mcp"],
      "env": {
        "BING_WEBMASTER_API_KEY": "<your-bing-api-key>",
        "BING_DEFAULT_SITE_URL": "https://example.com/"
      }
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "bing-webmaster": {
      "command": "uvx",
      "args": ["--from", "bing-webmaster-mcp", "bing-webmaster-mcp"],
      "env": {
        "BING_WEBMASTER_API_KEY": "<your-bing-api-key>",
        "BING_DEFAULT_SITE_URL": "https://example.com/"
      }
    }
  }
}
```

### CLI / Shell
```bash
export BING_WEBMASTER_API_KEY="<your-bing-api-key>"
export BING_DEFAULT_SITE_URL="https://example.com/"
uvx --from bing-webmaster-mcp bing-webmaster-mcp
```

---

## 4. Setting Up IndexNow Instant Indexing

IndexNow allows instant discovery by Bing, Yandex, Seznam, and Naver without waiting for crawlers.

1. **Generate an IndexNow Key**:
   Create a random 32-character hexadecimal key:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(16))"
   ```
2. **Host the Verification File**:
   Host the key at the root of your web domain:
   - URL: `https://<yourdomain.com>/<key>.txt`
   - Content: Exact string matching `<key>`
   - Example: `https://example.com/37bf60d90d8a4369a4c845b42d765ee2.txt`
3. **Submit URLs via MCP**:
   Call `indexnow_submit_urls`:
   ```python
   indexnow_submit_urls(
       host="example.com",
       key="37bf60d90d8a4369a4c845b42d765ee2",
       url_list=["https://example.com/new-article", "https://example.com/updated-guide"]
   )
   ```

---

## 5. Common Errors & Troubleshooting

- **401 Unauthorized**:
  - The `BING_WEBMASTER_API_KEY` is missing or invalid. Check that the key copied from `https://www.bing.com/webmasters/configure/apimanagement/apikey` matches exactly.
- **Site Not Verified (`IsVerified: false`)**:
  - Open Bing Webmaster Tools console and complete site verification (via DNS TXT record, HTML file upload, or GSC import).
- **IndexNow Key 403 Forbidden**:
  - Verify that `https://<host>/<key>.txt` returns HTTP 200 with `Content-Type: text/plain` and contains only the key with no extra HTML tags.
