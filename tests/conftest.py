# SPDX-License-Identifier: MIT
"""Deterministic test fixtures and mock Bing API / IndexNow responses."""
import json
import pytest

MOCK_USER_SITES = {
    "d": [
        {
            "__type": "Site:#Microsoft.Bing.Webmaster.Api",
            "AuthenticationCode": "A1B2C3D4E5F67890",
            "DnsVerificationCode": "a1b2c3d4e5f67890.surendranb.com",
            "IsVerified": True,
            "Url": "https://surendranb.com",
        },
        {
            "__type": "Site:#Microsoft.Bing.Webmaster.Api",
            "AuthenticationCode": "F1E2D3C4B5A67890",
            "DnsVerificationCode": "f1e2d3c4b5a67890.freeinference.dev",
            "IsVerified": True,
            "Url": "https://freeinference.dev",
        },
        {
            "__type": "Site:#Microsoft.Bing.Webmaster.Api",
            "AuthenticationCode": "1234567890ABCDEF",
            "DnsVerificationCode": "1234567890abcdef.builditwithai.xyz",
            "IsVerified": True,
            "Url": "https://builditwithai.xyz",
        },
    ]
}

MOCK_QUERY_STATS = {
    "https://surendranb.com": {
        "d": [
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 32,
                "AvgImpressionPosition": 45,
                "Clicks": 42,
                "Date": "/Date(1760659200000)/",
                "Impressions": 520,
                "Query": "running coach ai",
            },
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 12,
                "AvgImpressionPosition": 15,
                "Clicks": 18,
                "Date": "/Date(1760659200000)/",
                "Impressions": 95,
                "Query": "surendran balachandran",
            },
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 54,
                "AvgImpressionPosition": 62,
                "Clicks": 9,
                "Date": "/Date(1760659200000)/",
                "Impressions": 140,
                "Query": "desk biome",
            },
        ]
    },
    "https://freeinference.dev": {
        "d": [
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 24,
                "AvgImpressionPosition": 30,
                "Clicks": 320,
                "Date": "/Date(1760659200000)/",
                "Impressions": 4500,
                "Query": "free deepseek api",
            },
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 18,
                "AvgImpressionPosition": 22,
                "Clicks": 180,
                "Date": "/Date(1760659200000)/",
                "Impressions": 2200,
                "Query": "free llm inference",
            },
        ]
    },
    "https://builditwithai.xyz": {
        "d": [
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 28,
                "AvgImpressionPosition": 35,
                "Clicks": 110,
                "Date": "/Date(1760659200000)/",
                "Impressions": 1500,
                "Query": "mcp servers",
            },
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 15,
                "AvgImpressionPosition": 20,
                "Clicks": 65,
                "Date": "/Date(1760659200000)/",
                "Impressions": 820,
                "Query": "build it with ai",
            },
        ]
    },
}

MOCK_PAGE_STATS = {
    "https://surendranb.com": {
        "d": [
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 25,
                "AvgImpressionPosition": 35,
                "Clicks": 50,
                "Date": "/Date(1760659200000)/",
                "Impressions": 600,
                "Query": "https://surendranb.com/",
            },
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 15,
                "AvgImpressionPosition": 20,
                "Clicks": 19,
                "Date": "/Date(1760659200000)/",
                "Impressions": 155,
                "Query": "https://surendranb.com/about",
            },
        ]
    },
    "https://freeinference.dev": {
        "d": [
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 21,
                "AvgImpressionPosition": 28,
                "Clicks": 500,
                "Date": "/Date(1760659200000)/",
                "Impressions": 6700,
                "Query": "https://freeinference.dev/",
            }
        ]
    },
    "https://builditwithai.xyz": {
        "d": [
            {
                "__type": "QueryStats:#Microsoft.Bing.Webmaster.Api",
                "AvgClickPosition": 23,
                "AvgImpressionPosition": 31,
                "Clicks": 175,
                "Date": "/Date(1760659200000)/",
                "Impressions": 2320,
                "Query": "https://builditwithai.xyz/",
            }
        ]
    },
}

MOCK_CRAWL_ISSUES = {
    "https://surendranb.com": {
        "d": [
            {
                "Url": "https://surendranb.com/old-page",
                "HttpCode": 404,
                "Issues": "Page Not Found",
                "InLinks": 3,
            }
        ]
    },
    "https://freeinference.dev": {"d": []},
    "https://builditwithai.xyz": {
        "d": [
            {
                "Url": "https://builditwithai.xyz/broken",
                "HttpCode": 500,
                "Issues": "Internal Server Error",
                "InLinks": 1,
            }
        ]
    },
}
