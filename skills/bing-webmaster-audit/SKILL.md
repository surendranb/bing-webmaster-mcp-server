---
name: bing-webmaster-audit
description: "Step-by-step diagnostic strategy for auditing organic search visibility, query rankings, and crawl hygiene using Bing Webmaster Tools MCP."
---

# Bing Webmaster Audit Playbook

Step-by-step diagnostic strategy for auditing organic search visibility, query rankings, and crawl hygiene using Bing Webmaster Tools MCP.

## Workflow

1. **Verify Verified Sites**:
   - Call `get_user_sites()` to list all properties registered under your Bing Webmaster account.
   - Confirm your target domain is listed with `IsVerified: true`.

2. **Evaluate Search Queries**:
   - Call `get_query_stats(site_url="https://yourdomain.com")`.
   - Inspect high-impression, low-click queries (CTR optimization opportunities).
   - Check average click position and impression position.

3. **Inspect Top Pages**:
   - Call `get_page_stats(site_url="https://yourdomain.com")`.
   - Identify which URLs capture the bulk of organic traffic.
   - Look for decaying pages that have dropped in impressions.

4. **Investigate Crawl & Indexing Blockers**:
   - Call `get_crawl_issues(site_url="https://yourdomain.com")`.
   - Group issues by HTTP status code (404 Not Found, 500 Server Error, DNS failures).
   - Prioritize pages with high in-link counts (`InLinks`).

5. **Instant Indexing of Fresh Content**:
   - When new content or fixes are published, submit the URLs immediately with `submit_urls(site_url=..., urls=[...])` to notify Bing and IndexNow-participating engines.
