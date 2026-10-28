---
name: indexnow-instant-indexing
description: "How to use the IndexNow open protocol and Bing Webmaster API to notify search engines immediately whenever content is added, updated, or removed."
---

# IndexNow Instant Indexing Protocol Playbook

How to use the IndexNow open protocol and Bing Webmaster API to notify search engines immediately whenever content is added, updated, or removed.

## What is IndexNow?

IndexNow is an open protocol created by Microsoft Bing and Yandex, and supported by search engines like Seznam and Naver. A single ping to IndexNow propagates across all participating search engines simultaneously.

## Setup Requirements

1. **API Key & Host**:
   - Generate an IndexNow key (8-128 hex characters or standard UUID).
   - Place a text file named `{your-key}.txt` in your site's root directory containing only the key.
   - Example: `https://example.com/258CAD36B9EEE22F1CFDEB4C239D26BB.txt` containing `258CAD36B9EEE22F1CFDEB4C239D26BB`.

2. **Environment Variable Configuration**:
   - Set `INDEXNOW_KEY="your-indexnow-key"` in your environment, or pass `indexnow_key` directly to `submit_urls`.
   - Optionally set `BING_WEBMASTER_API_KEY="your-bing-key"` for dual submission.

3. **Submitting URLs**:
   - Call `submit_urls(site_url="https://example.com", urls=["https://example.com/new-article"])`.
   - The MCP server sends both:
     1. A batch submission to Bing Webmaster Tools API (`SubmitUrlbatch`)
     2. A JSON POST to IndexNow protocol (`https://api.indexnow.org/indexnow`)
