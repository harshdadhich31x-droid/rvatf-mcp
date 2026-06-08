import os
import json
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

API_KEY = os.environ.get("RVATF_API_KEY", "change-me")
BASE_URL = os.environ.get("BASE_URL", "https://rvatf-mcp.onrender.com")
REGISTERED_CLIENTS = {}

# RVATF Mindset Framework
MINDSETS = [
    {
        "rank": 1,
        "name": "Risk-first",
        "why": "With MTF leverage + one concentrated position, you die from risk failures, not signal failures. Survival before return.",
        "practice": "Always ask 'what's my worst case?' before 'what's my profit?' Size for the gap, respect the stop, never override."
    },
    {
        "rank": 2,
        "name": "Systematic / probabilistic",
        "why": "Your whole system is rules played repeatedly. You're buying an edge over many trades, not 'calling' a stock.",
        "practice": "Think in win rate, expectancy, R-multiples — distributions, not predictions. One trade's outcome means nothing; 200 do."
    },
    {
        "rank": 3,
        "name": "Scientific / skeptical",
        "why": "You must be willing to kill your own strategy if data says it has no edge. Falling in love with it loses money.",
        "practice": "Treat every belief as a hypothesis to disprove. Confirmation bias is the trader-killer."
    },
    {
        "rank": 4,
        "name": "Behavioral discipline",
        "why": "You already felt it — 'hold the quality stock that gapped.' The system's biggest enemy is you overriding it.",
        "practice": "Pre-commit to rules; remove your own discretion (that's why the auto-stop exists). Beat fear, greed, revenge."
    },
    {
        "rank": 5,
        "name": "Patience / process",
        "why": "One position + wait-for-setup means sitting in cash is the correct move most days. Overtrading kills accounts.",
        "practice": "'No trade' is a position. Play the long game (you said build for the end)."
    },
    {
        "rank": 6,
        "name": "Engineering reliability",
        "why": "It's automated — a bug, outage, or unhandled error at the wrong moment = real loss.",
        "practice": "Build for failure: error handling, kill switch, monitoring, secrets safety. Assume things break."
    }
]

KNOWLEDGE_DOMAINS = [
    {"id": 7, "domain": "Statistics (sample size, overfitting, signal vs noise)", "why": "To tell a real edge from a curve-fit backtest. The single skill that separates winners from the deluded."},
    {"id": 8, "domain": "Backtesting method (look-ahead bias, out-of-sample, reproducibility)", "why": "A flawed backtest gives false confidence and loses live money."},
    {"id": 9, "domain": "Costs & microstructure (slippage, spreads, liquidity, fills)", "why": "Small-target swing systems live or die on costs — a 'profitable' backtest can be a live loser."},
    {"id": 10, "domain": "Market mechanics (NSE, T+1, MTF margin, circuits, sessions, F&O influence)", "why": "You must know the plumbing you trade in."},
    {"id": 11, "domain": "Capital & compounding math (drawdown recovery, position-sizing math)", "why": "How ₹10L actually survives and grows; a 50% loss needs 100% gain to recover."},
    {"id": 12, "domain": "Regulation (SEBI algo framework, broker terms)", "why": "Stay legal — and essential if you ever commercialize."},
    {"id": 13, "domain": "Edge-decay awareness / live-vs-backtest monitoring", "why": "The meta-skill veterans learn the hard way: a working edge stops working. Track live results against backtest expectations and know when it breaks."},
    {"id": 14, "domain": "Data integrity", "why": "Survivorship bias, corporate-action adjustment, clean data. Bad data = a beautiful backtest that's pure fiction."}
]

RISK_RULES = {
    "framework": "RVATF - Risk-Validated Automated Trading Framework",
    "core_principles": [
        "Risk before return — size for survival, not profit",
        "1% max risk per trade (hard limit)",
        "One position at a time (concentrated but controlled)",
        "MTF leverage — know your margin, gap risk, interest cost",
        "Auto-stop mandatory — no discretion to override",
        "Kill switch enabled — circuit breaker for disaster",
        "Cash is a position — most days you do nothing"
    ],
    "forbidden_behaviors": [
        "Overriding stops based on 'feeling'",
        "Revenge trading after a loss",
        "Doubling position size to 'make it back'",
        "Trading without a setup",
        "Ignoring costs/slippage in backtest"
    ]
}

PREP_CHECKLIST = [
    "Get clean historical price data for backtest (the #1 prerequisite)",
    "Learn backtesting pitfalls (look-ahead, overfitting) — or your backtest lies to you",
    "Verify Dhan account + API access and read MTF terms (interest slab, margin-call mechanics)",
    "Write down your 'edge proven' bar — exact numbers (win rate, expectancy, max DD) that mean go/no-go",
    "Internalize the risk rules until you won't override them under stress"
]

RESOURCES = [
    {"name": "Zerodha Varsity", "topics": "Technical analysis, markets, trading psychology", "why": "Free, India-specific, excellent starting point"},
    {"name": "Van Tharp - Trade Your Way to Financial Freedom", "topics": "Expectancy, position sizing, psychology", "why": "Core mindset and risk framework"},
    {"name": "Ernie Chan - Quantitative Trading", "topics": "Backtesting and quant method", "why": "How to test an edge properly"},
    {"name": "Daniel Kahneman - Thinking, Fast and Slow", "topics": "Cognitive biases", "why": "The biases you're fighting in yourself"}
]

TOOLS_LIST = [
    {
        "name": "get_mindsets",
        "description": "Get the 6 core RVATF mindsets ranked by importance (risk-first, systematic, scientific, behavioral, patience, engineering)",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_knowledge_domains",
        "description": "Get the 8 knowledge domains required for RVATF (statistics, backtesting, costs, markets, capital math, regulation, edge-decay, data integrity)",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_risk_rules",
        "description": "Get RVATF core risk rules (1% max risk, one position, auto-stop, kill switch, forbidden behaviors)",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_prep_checklist",
        "description": "Get the 5-step prep checklist before building RVATF system",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_resources",
        "description": "Get recommended learning resources (books, courses) for RVATF mindset and knowledge",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "check_decision",
        "description": "Check if a trading decision aligns with RVATF mindset and rules",
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "description": "The trading decision or thought to validate"}
            },
            "required": ["decision"]
        }
    },
    {
        "name": "get_mindset_reminder",
        "description": "Get a specific mindset reminder by name (risk-first, systematic, scientific, behavioral, patience, engineering)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mindset_name": {"type": "string", "description": "Name of mindset (e.g., 'risk-first', 'behavioral')"}
            },
            "required": ["mindset_name"]
        }
    }
]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def mcp_response(req_id, result):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "result": result})

def mcp_error(req_id, code, message):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})

def execute_tool(name, args):
    if name == "get_mindsets":
        return {"mindsets": MINDSETS, "count": len(MINDSETS), "time": now_iso()}
    
    if name == "get_knowledge_domains":
        return {"domains": KNOWLEDGE_DOMAINS, "count": len(KNOWLEDGE_DOMAINS), "time": now_iso()}
    
    if name == "get_risk_rules":
        return {"risk_rules": RISK_RULES, "time": now_iso()}
    
    if name == "get_prep_checklist":
        return {"checklist": PREP_CHECKLIST, "count": len(PREP_CHECKLIST), "time": now_iso()}
    
    if name == "get_resources":
        return {"resources": RESOURCES, "count": len(RESOURCES), "time": now_iso()}
    
    if name == "check_decision":
        decision = args.get("decision", "")
        analysis = f"Checking decision against RVATF mindset: '{decision}'\n\n"
        
        violations = []
        if "override" in decision.lower() or "ignore stop" in decision.lower():
            violations.append("VIOLATION: Behavioral discipline - never override stops")
        if "double" in decision.lower() or "increase size" in decision.lower():
            violations.append("VIOLATION: Risk-first - never increase size to recover losses")
        if "revenge" in decision.lower():
            violations.append("VIOLATION: Behavioral discipline - revenge trading forbidden")
        
        if violations:
            analysis += "⚠️ VIOLATIONS DETECTED:\n" + "\n".join(violations)
        else:
            analysis += "✓ No obvious violations detected. Remember: think risk-first, systematic, and stay disciplined."
        
        return {"decision": decision, "analysis": analysis, "time": now_iso()}
    
    if name == "get_mindset_reminder":
        mindset_name = args.get("mindset_name", "").lower()
        found = None
        for m in MINDSETS:
            if mindset_name in m["name"].lower():
                found = m
                break
        
        if not found:
            raise ValueError(f"Mindset '{mindset_name}' not found. Available: risk-first, systematic, scientific, behavioral, patience, engineering")
        
        return {"mindset": found, "time": now_iso()}
    
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
    return jsonify({"ok": True, "service": "rvatf-mindset-mcp", "time": now_iso()})

@app.route("/", methods=["POST", "GET"])
@app.route("/mcp", methods=["POST", "GET"])
def mcp_endpoint():
    if request.method == "GET":
        return jsonify({
            "name": "RVATF Mindset Connector",
            "version": "2.0.0",
            "description": "RVATF trading mindset framework for disciplined systematic trading"
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
                "name": "RVATF Mindset Connector",
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
