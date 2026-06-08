import os
import json
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

API_KEY = os.environ.get("RVATF_API_KEY", "change-me")
BASE_URL = os.environ.get("BASE_URL", "https://rvatf-mcp.onrender.com")

REGISTERED_CLIENTS = {}

WATCHLIST = [
    {"symbol": "RELIANCE", "segment": "NSE_EQ", "enabled": True},
    {"symbol": "HDFCBANK", "segment": "NSE_EQ", "enabled": True},
    {"symbol": "INFY", "segment": "NSE_EQ", "enabled": True},
    {"symbol": "TCS", "segment": "NSE_EQ", "enabled": True},
    {"symbol": "ICICIBANK", "segment": "NSE_EQ", "enabled": True},
    {"symbol": "AXISBANK", "segment": "NSE_EQ", "enabled": True},
    {"symbol": "SBIN", "segment": "NSE_EQ", "enabled": True},
    {"symbol": "BAJFINANCE", "segment": "NSE_EQ", "enabled": True},
    {"symbol": "WIPRO", "segment": "NSE_EQ", "enabled": True},
    {"symbol": "HCLTECH", "segment": "NSE_EQ", "enabled": True},
]

BACKTESTS = {
    "mtf_swing_v1": {
        "strategy": "mtf_swing_v1",
        "trades": 214,
        "win_rate": 0.47,
        "avg_win_r": 2.1,
        "avg_loss_r": -1.0,
        "expectancy_r": 0.17,
        "max_drawdown_pct": 11.8,
        "profit_factor": 1.42,
        "out_of_sample_passed": True,
    }
}

RISK_RULES = {
    "framework": "RVATF",
    "broker": "Dhan",
    "market": "NSE",
    "product": "MTF",
    "max_positions": 1,
    "max_risk_per_trade_pct": 1.0,
    "kill_switch_enabled": True,
    "override_allowed": False,
}

POSITIONS = [
    {
        "symbol": "RELIANCE",
        "qty": 10,
        "avg_price": 2940.5,
        "last_price": 2962.0,
        "unrealized_pnl": 215.0,
        "product": "MTF",
        "risk_state": "within_limits",
    }
]

JOURNAL = [
    {"id": "t001", "symbol": "INFY", "result_r": 1.8, "date": "2026-06-01", "followed_rules": True},
    {"id": "t002", "symbol": "TCS", "result_r": -1.0, "date": "2026-06-03", "followed_rules": True},
]

TOOLS_LIST = [
    {
        "name": "get_watchlist",
        "description": "Get RVATF tracked NSE symbols",
        "inputSchema": {
            "type": "object",
            "properties": {
                "enabled_only": {"type": "boolean", "description": "Filter enabled symbols only"}
            }
        }
    },
    {
        "name": "get_risk_rules",
        "description": "Get current RVATF risk and control rules",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_backtest_summary",
        "description": "Get backtest summary for a strategy",
        "inputSchema": {
            "type": "object",
            "properties": {
                "strategy": {"type": "string", "description": "Strategy name e.g. mtf_swing_v1"}
            },
            "required": ["strategy"]
        }
    },
    {
        "name": "get_live_positions",
        "description": "Get current live trading positions",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_trade_journal",
        "description": "Get recent trade journal entries",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of entries to return"}
            }
        }
    },
    {
        "name": "get_system_status",
        "description": "Get RVATF system and risk guard status",
        "inputSchema": {"type": "object", "properties": {}}
    }
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def mcp_response(req_id, result):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "result": result})


def mcp_error(req_id, code, message):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def execute_tool(name, args):
    if name == "get_watchlist":
        enabled_only = args.get("enabled_only", False)
        items = [x for x in WATCHLIST if x["enabled"]] if enabled_only else WATCHLIST
        return {"count": len(items), "items": items, "time": now_iso()}
    if name == "get_risk_rules":
        return {"rules": RISK_RULES, "time": now_iso()}
    if name == "get_backtest_summary":
        strategy = args.get("strategy")
        result = BACKTESTS.get(strategy)
        if not result:
            raise ValueError(f"Unknown strategy: {strategy}")
        return {"summary": result, "time": now_iso()}
    if name == "get_live_positions":
        return {"count": len(POSITIONS), "positions": POSITIONS, "time": now_iso()}
    if name == "get_trade_journal":
        limit = int(args.get("limit", 20))
        return {"count": min(limit, len(JOURNAL)), "items": JOURNAL[:limit], "time": now_iso()}
    if name == "get_system_status":
        return {
            "framework": "RVATF",
            "mode": "read-only",
            "kill_switch": True,
            "max_positions": 1,
            "time": now_iso()
        }
    raise ValueError(f"Unknown tool: {name}")


@app.route("/.well-known/oauth-authorization-server", methods=["GET"])
@app.route("/.well-known/oauth-authorization-server/", methods=["GET"])
def oauth_metadata():
    return jsonify({
        "issuer": BASE_URL,
        "authorization_endpoint": f"{BASE_URL}/authorize",
        "token_endpoint": f"{BASE_URL}/token",
        "registration_endpoint": f"{BASE_URL}/register",
        "scopes_supported": ["mcp"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "client_credentials"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_basic"],
        "code_challenge_methods_supported": ["S256"],
    })


@app.route("/register", methods=["POST"])
def register_client():
    body = request.get_json(force=True, silent=True) or {}
    client_id = str(uuid.uuid4())
    client_secret = str(uuid.uuid4())
    REGISTERED_CLIENTS[client_id] = {
        "client_secret": client_secret,
        "redirect_uris": body.get("redirect_uris", []),
        "client_name": body.get("client_name", "MCP Client"),
        "grant_types": body.get("grant_types", ["authorization_code"]),
        "response_types": body.get("response_types", ["code"]),
        "scope": body.get("scope", "mcp"),
    }
    resp = {
        "client_id": client_id,
        "client_secret": client_secret,
        "client_id_issued_at": int(datetime.now(timezone.utc).timestamp()),
        "client_secret_expires_at": 0,
        "redirect_uris": REGISTERED_CLIENTS[client_id]["redirect_uris"],
        "client_name": REGISTERED_CLIENTS[client_id]["client_name"],
        "grant_types": REGISTERED_CLIENTS[client_id]["grant_types"],
        "response_types": REGISTERED_CLIENTS[client_id]["response_types"],
        "scope": REGISTERED_CLIENTS[client_id]["scope"],
        "token_endpoint_auth_method": "none",
    }
    return jsonify(resp), 201


@app.route("/authorize", methods=["GET"])
def authorize():
    redirect_uri = request.args.get("redirect_uri", "")
    state = request.args.get("state", "")
    code = str(uuid.uuid4())
    sep = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{sep}code={code}&state={state}"
    return Response(status=302, headers={"Location": location})


@app.route("/token", methods=["POST"])
def token():
    return jsonify({
        "access_token": "rvatf-static-token",
        "token_type": "Bearer",
        "expires_in": 86400,
        "scope": "mcp",
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "rvatf-mcp", "time": now_iso()})


@app.route("/", methods=["POST", "GET"])
@app.route("/mcp", methods=["POST", "GET"])
def mcp_endpoint():
    if request.method == "GET":
        return jsonify({
            "name": "RVATF MCP Connector",
            "version": "2.0.0",
            "description": "RVATF trading framework connector for NSE markets"
        })

    data = request.get_json(force=True, silent=True) or {}
    method = data.get("method", "")
    req_id = data.get("id", 1)
    params = data.get("params", {})

    if method == "initialize":
        return mcp_response(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False}
            },
            "serverInfo": {
                "name": "RVATF MCP Connector",
                "version": "2.0.0"
            }
        })

    if method == "notifications/initialized":
        return Response(status=204)

    if method == "tools/list":
        return mcp_response(req_id, {"tools": TOOLS_LIST})

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        try:
            result = execute_tool(tool_name, tool_args)
            return mcp_response(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
            })
        except ValueError as e:
            return mcp_error(req_id, -32602, str(e))
        except Exception as e:
            return mcp_error(req_id, -32603, str(e))

    if method == "ping":
        return mcp_response(req_id, {})

    return mcp_error(req_id, -32601, f"Method not found: {method}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8787))
    app.run(host="0.0.0.0", port=port)
