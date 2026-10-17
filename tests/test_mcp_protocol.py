# SPDX-License-Identifier: MIT
"""Native MCP protocol stdio JSON-RPC test.

Proves end-to-end protocol compatibility by spawning the server subprocess
and executing JSON-RPC handshake, tools/list, and tools/call.
"""
import json
import os
import subprocess
import sys
import time
import pytest


def _read_json_rpc(proc: subprocess.Popen, timeout: float = 5.0) -> dict:
    start = time.time()
    line = ""
    while time.time() - start < timeout:
        raw = proc.stdout.readline()
        if raw:
            line = raw.decode("utf-8").strip()
            if line:
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for JSON-RPC response from server. Last line: {line!r}")


def _write_json_rpc(proc: subprocess.Popen, payload: dict):
    msg = json.dumps(payload) + "\n"
    proc.stdin.write(msg.encode("utf-8"))
    proc.stdin.flush()


def test_native_mcp_stdio_jsonrpc():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath("src")
    env["MCP_TELEMETRY_OPT_OUT"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "bing_webmaster_mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    try:
        # 1. initialize handshake
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "native-tester", "version": "1.0"},
            },
        }
        _write_json_rpc(proc, init_req)
        init_res = _read_json_rpc(proc)

        assert init_res.get("id") == 1
        assert "result" in init_res
        server_info = init_res["result"].get("serverInfo", {})
        assert server_info.get("name") == "bing-webmaster-mcp"

        # 2. initialized notification
        init_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        _write_json_rpc(proc, init_notif)

        # 3. tools/list
        tools_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        _write_json_rpc(proc, tools_req)
        tools_res = _read_json_rpc(proc)

        assert tools_res.get("id") == 2
        tools = tools_res["result"]["tools"]
        tool_names = {t["name"] for t in tools}

        expected_tools = {
            "get_user_sites",
            "get_query_stats",
            "get_page_stats",
            "get_crawl_issues",
            "submit_urls",
            "doctor",
            "skills_list",
            "skill_read",
            "check_for_updates",
        }
        missing = expected_tools - tool_names
        assert not missing, f"Server did not expose expected tools: {missing}"

        # 4. tools/call -> doctor
        call_doc = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "doctor",
                "arguments": {},
            },
        }
        _write_json_rpc(proc, call_doc)
        doc_res = _read_json_rpc(proc)

        assert doc_res.get("id") == 3
        doc_content = doc_res["result"]["content"][0]["text"]
        assert "bing-webmaster-mcp" in doc_content
        assert "diagnostics" in doc_content

        # 5. tools/call -> skills_list
        call_skills = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "skills_list",
                "arguments": {},
            },
        }
        _write_json_rpc(proc, call_skills)
        skills_res = _read_json_rpc(proc)

        assert skills_res.get("id") == 4
        skills_content = skills_res["result"]["content"][0]["text"]
        assert "bing-webmaster-audit" in skills_content

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
