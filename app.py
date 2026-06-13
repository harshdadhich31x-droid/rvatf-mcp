import os
import json
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

API_KEY = os.environ.get("RVATF_API_KEY", "change-me")
BASE_URL = os.environ.get("BASE_URL", "https://rvatf-mcp.onrender.com")
REGISTERED_CLIENTS = {}

# Version
VERSION = "2.0"

# RVATF Mindset Framework (v2 - corrected)
MINDSETS = [
    {
        "rank": 1,
        "name": "Risk-first",
        "why": "With MTF leverage + one concentrated position, you die from risk failures, not signal failures. Survival before return.",
        "practice": "Always ask 'what's my worst case?' before 'what's my profit?' Size for the gap, respect the stop, never override.",
        "rules": [
            "Size via min(stop-risk, gap-risk, exposure-cap)",
            "Never widen SL after entry",
            "Position size must respect 8% gap-loss cap",
            "Max 1% risk per trade (or 0.5% during early live)"
        ],
        "violations": ["Widening stop mid-trade", "Sizing only on stop without gap check", "Overriding stop based on conviction"]
    },
    {
        "rank": 2,
        "name": "Systematic / probabilistic",
        "why": "Your whole system is rules played repeatedly. You're buying an edge over many trades, not 'calling' a stock.",
        "practice": "Think in win rate, expectancy, R-multiples — distributions, not predictions. One trade's outcome means nothing; 200 do.",
        "rules": [
            "Every decision must be rule-based, not discretionary",
            "Track expectancy in R-multiples",
            "100+ trades minimum for edge validation"
        ],
        "violations": ["Discretionary overrides", "Judging system on last 5 trades", "Changing rules mid-stream"]
    },
    {
        "rank": 3,
        "name": "Scientific / skeptical",
        "why": "You must be willing to kill your own strategy if data says it has no edge. Falling in love with it loses money.",
        "practice": "Treat every belief as a hypothesis to disprove. Confirmation bias is the trader-killer.",
        "rules": [
            "Pre-define go/no-go thresholds before backtest",
            "Use out-of-sample testing",
            "Kill strategy if live expectancy ≤ 0 for 50+ trades"
        ],
        "violations": ["Moving goalposts after seeing results", "Ignoring negative data", "Rationalizing losses"]
    },
    {
        "rank": 4,
        "name": "Behavioral discipline",
        "why": "You already felt it — 'hold the quality stock that gapped.' The system's biggest enemy is you overriding it.",
        "practice": "Pre-commit to rules; remove your own discretion (that's why the auto-stop exists). Beat fear, greed, revenge.",
        "rules": [
            "No discretionary stop removal",
            "No revenge trading after loss",
            "Auto-stop is hardcoded, not optional"
        ],
        "violations": ["Removing stops manually", "Doubling size to recover", "Revenge trading"]
    },
    {
        "rank": 5,
        "name": "Patience / process",
        "why": "One position + wait-for-setup means sitting in cash is the correct move most days. Overtrading kills accounts.",
        "practice": "'No trade' is a position. Play the long game (you said build for the end).",
        "rules": [
            "Only enter on high-conviction setup",
            "Skip days when no clean entry",
            "Cash is a position"
        ],
        "violations": ["Forcing trades", "Lowering entry standards", "Chasing missed entries"]
    },
    {
        "rank": 6,
        "name": "Engineering reliability",
        "why": "It's automated — a bug, outage, or unhandled error at the wrong moment = real loss.",
        "practice": "Build for failure: error handling, kill switch, monitoring, secrets safety. Assume things break.",
        "rules": [
            "Every API call must have error handling",
            "Kill switch is mandatory",
            "Log every trade decision",
            "Secrets via env vars, never hardcoded"
        ],
        "violations": ["Skipping error handling", "No kill switch", "Hardcoded credentials"]
    }
]

KNOWLEDGE_DOMAINS = [
    {"id": 7, "domain": "Statistics (sample size, overfitting, signal vs noise)", "why": "To tell a real edge from a curve-fit backtest. 100+ trades minimum for significance."},
    {"id": 8, "domain": "Backtesting method (look-ahead bias, out-of-sample, reproducibility)", "why": "A flawed backtest gives false confidence and loses live money."},
    {"id": 9, "domain": "Costs & microstructure (slippage, spreads, liquidity, MTF interest)", "why": "Small-target swing systems live or die on costs. MTF interest = 0.0342%/day (Dhan base slab). Total drag ≈0.3% per round trip."},
    {"id": 10, "domain": "Market mechanics (NSE, T+1, MTF margin, circuits, stock-specific price bands)", "why": "Stock price bands are 2/5/10/20% (not index 10/15/20%). Your stop may not execute if band hit."},
    {"id": 11, "domain": "Capital & compounding math (drawdown recovery, gap-aware position sizing)", "why": "A 50% loss needs 100% gain to recover. Size formula: min(stop-risk, gap-risk, exposure-cap)."},
    {"id": 12, "domain": "Regulation (SEBI algo framework, broker MTF terms, personal-use vs marketplace)", "why": "Personal algo use allowed; selling requires RA license + exchange approval (April 2026+ rules)."},
    {"id": 13, "domain": "Edge-decay awareness / live-vs-backtest monitoring", "why": "Edges decay. Track rolling 30-trade expectancy; pause if ≤0."},
    {"id": 14, "domain": "Data integrity (survivorship bias, corporate actions, data source quality)", "why": "Bad data = beautiful backtest that's pure fiction. Use NSE/broker data, adjusted for splits/dividends."}
]

# Execution Rules (v2 - your 7 rules, corrected)
EXECUTION_RULES = [
    {
        "rule_id": 1,
        "name": "Position sizing",
        "summary": "Use 70-85% of capital per trade, but bounded by risk/gap/exposure caps",
        "formula": "shares = min(N_stop, N_gap, N_expo) where N_stop = risk/(Se - Ss), N_gap = (gap_cap * C)/(gap_% * Se), N_expo = E_max/Se",
        "parameters": {
            "capital_C": "10L",
            "risk_per_trade": "0.5-1%",
            "gap_assumption": "8%",
            "gap_loss_cap": "4% of equity",
            "max_exposure_E": "15L notional"
        }
    },
    {
        "rule_id": 2,
        "name": "Missed entry handling",
        "summary": "If all candidates gap above entry zone or hit SL/target before entry window, skip the day",
        "action": "NO-TRADE; log reason; observe market; do not chase"
    },
    {
        "rule_id": 3,
        "name": "Stop loss",
        "summary": "Hard SL via Dhan Super Order, 1.2-1.5% based on ATR; never widen after entry",
        "details": [
            "Place hard SL at entry (not mental)",
            "SL width: 1.2-1.5% (based on stock ATR)",
            "After T1: move SL to entry (breakeven)",
            "After T2: move SL to T1 area",
            "Then: trail at max(1%, 1.5*ATR) below price"
        ]
    },
    {
        "rule_id": 4,
        "name": "Profit booking",
        "summary": "T1=+1.5% (book 30%), T2=+2.5% (book 30%), trail remaining 40%",
        "targets": {
            "T1": "+1.5% — book 30%, move SL to entry",
            "T2": "+2.5% — book 30%, move SL to T1",
            "Trail": "Remaining 40% with trailing_distance = max(1%, 1.5*ATR)"
        }
    },
    {
        "rule_id": 5,
        "name": "No-trade days",
        "summary": "Skip days with no high-conviction setup; cash is a position",
        "action": "Log NO-TRADE reason; learn from the day; do not force entries"
    },
    {
        "rule_id": 6,
        "name": "Max concurrent positions",
        "summary": "1 position at a time (concentrated, high-quality)",
        "enforcement": "If 1 position open, block all new entries until exit"
    },
    {
        "rule_id": 7,
        "name": "News during trade",
        "summary": "Red news (fraud, bad results) → exit immediately; Green news (strong positive) → skip T1 booking, trail from T2; Grey news → ignore",
        "buckets": {
            "red": "Exit at market, log reason",
            "green": "Skip T1 exit, book 30-40% at T2, trail rest",
            "grey": "Do nothing, follow normal rules"
        },
        "constraint": "Never loosen SL on news, only tighten or exit"
    }
]

RISK_RULES = {
    "framework": "RVATF v2 - Risk-Validated Automated Trading Framework",
    "version": VERSION,
    "core_principles": [
        "Risk before return — size for survival, not profit",
        "1% max risk per trade (0.5% during live rollout)",
        "One position at a time (concentrated but controlled)",
        "Gap-aware sizing: size so 8% gap ≤ 4% equity loss",
        "MTF leverage: max ~4x, never full leverage on full capital",
        "Auto-stop mandatory — no discretion to override",
        "Kill switch: flatten position + halt new orders (never cancel stops)",
        "Cash is a position — most days you do nothing"
    ],
    "forbidden_behaviors": [
        "Widening SL after entry",
        "Overriding stops based on 'feeling'",
        "Revenge trading after a loss",
        "Doubling position size to 'make it back'",
        "Trading without a setup",
        "Sizing without gap-risk check",
        "Ignoring costs/slippage in backtest"
    ],
    "kill_switch": {
        "triggers": [
            "Daily realised loss ≥ 2% of equity",
            "Drawdown from peak ≥ 15-20%",
            "3+ consecutive API failures",
            "Manual trigger"
        ],
        "action": "Set state=HALTED, flatten position at market (but keep stop as fallback), block new orders until manual reset"
    }
}

PREP_CHECKLIST = [
    "Get clean, adjusted historical data (5+ years NSE equity, corporate actions applied)",
    "Learn backtesting pitfalls (look-ahead, overfitting, survivorship bias)",
    "Verify Dhan account + API + MTF terms (interest = 0.0342%/day base slab)",
    "Write down go/no-go thresholds BEFORE backtest (min win rate, expectancy, max DD)",
    "Internalize risk rules until automatic (gap-cap, no SL widening, 1-position only)"
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
        "description": "Get the 6 core RVATF mindsets (v2) with rules and violation patterns",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_knowledge_domains",
        "description": "Get the 8 knowledge domains (v2) with corrected facts (MTF interest, circuits, etc)",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_risk_rules",
        "description": "Get RVATF v2 core risk rules (gap-aware sizing, kill switch spec, forbidden behaviors)",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_execution_rules",
        "description": "Get your 7 execution rules (sizing, SL, profit booking, news, etc) — v2 corrected",
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
        "description": "Check if a trading decision aligns with RVATF v2 mindset and rules",
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
        return {"version": VERSION, "mindsets": MINDSETS, "count": len(MINDSETS), "time": now_iso()}
    
    if name == "get_knowledge_domains":
        return {"version": VERSION, "domains": KNOWLEDGE_DOMAINS, "count": len(KNOWLEDGE_DOMAINS), "time": now_iso()}
    
    if name == "get_risk_rules":
        return {"version": VERSION, "risk_rules": RISK_RULES, "time": now_iso()}
    
    if name == "get_execution_rules":
        return {"version": VERSION, "execution_rules": EXECUTION_RULES, "count": len(EXECUTION_RULES), "time": now_iso()}
    
    if name == "get_prep_checklist":
        return {"version": VERSION, "checklist": PREP_CHECKLIST, "count": len(PREP_CHECKLIST), "time": now_iso()}
    
    if name == "get_resources":
        return {"version": VERSION, "resources": RESOURCES, "count": len(RESOURCES), "time": now_iso()}
    
    if name == "check_decision":
        decision = args.get("decision", "")
        analysis = f"Checking decision against RVATF v{VERSION}: '{decision}'\n\n"
        violations = []
        
        if "override" in decision.lower() or "ignore stop" in decision.lower():
            violations.append("⚠️  VIOLATION: Behavioral discipline — never override stops")
        if "widen" in decision.lower() and "stop" in decision.lower():
            violations.append("⚠️  VIOLATION: Risk-first — never widen SL after entry")
        if "double" in decision.lower() or "increase size" in decision.lower():
            violations.append("⚠️  VIOLATION: Risk-first — never increase size to recover losses")
        if "revenge" in decision.lower():
            violations.append("⚠️  VIOLATION: Behavioral discipline — revenge trading forbidden")
        if "chase" in decision.lower():
            violations.append("⚠️  VIOLATION: Patience — do not chase missed entries")
        
        if violations:
            analysis += "\n".join(violations)
        else:
            analysis += "✓ No obvious violations detected. Remember: think risk-first, systematic, and stay disciplined."
        
        return {"version": VERSION, "decision": decision, "analysis": analysis, "time": now_iso()}
    
    if name == "get_mindset_reminder":
        mindset_name = args.get("mindset_name", "").lower()
        found = None
        for m in MINDSETS:
            if mindset_name in m["name"].lower():
                found = m
                break
        
        if not found:
            raise ValueError(f"Mindset '{mindset_name}' not found. Available: risk-first, systematic, scientific, behavioral, patience, engineering")
        
        return {"version": VERSION, "mindset": found, "time": now_iso()}
    
    raise ValueError(f"Unknown tool: {name}")

# OAuth and MCP protocol endpoints
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
    return jsonify({"ok": True, "service": "rvatf-mcp", "version": VERSION, "time": now_iso()})

@app.route("/version", methods=["GET"])
def version():
    return jsonify({"service": "rvatf-mcp", "version": VERSION, "env": "render", "time": now_iso()})

# REST API Endpoints (for browsers/Perplexity)
@app.route("/api/mindsets", methods=["GET"])
def api_mindsets():
    return jsonify({"version": VERSION, "mindsets": MINDSETS, "count": len(MINDSETS), "time": now_iso()})

@app.route("/api/risk-rules", methods=["GET"])
def api_risk_rules():
    return jsonify({"version": VERSION, "risk_rules": RISK_RULES, "time": now_iso()})

@app.route("/api/knowledge", methods=["GET"])
def api_knowledge():
    return jsonify({"version": VERSION, "domains": KNOWLEDGE_DOMAINS, "count": len(KNOWLEDGE_DOMAINS), "time": now_iso()})

@app.route("/api/domains", methods=["GET"])
def api_domains():
    return jsonify({"version": VERSION, "domains": KNOWLEDGE_DOMAINS, "count": len(KNOWLEDGE_DOMAINS), "time": now_iso()})

@app.route("/api/rules", methods=["GET"])
def api_rules():
    return jsonify({"version": VERSION, "execution_rules": EXECUTION_RULES, "count": len(EXECUTION_RULES), "time": now_iso()})

@app.route("/api/prep", methods=["GET"])
def api_prep():
    return jsonify({"version": VERSION, "checklist": PREP_CHECKLIST, "count": len(PREP_CHECKLIST), "time": now_iso()})

@app.route("/api/resources", methods=["GET"])
def api_resources():
    return jsonify({"version": VERSION, "resources": RESOURCES, "count": len(RESOURCES), "time": now_iso()})

@app.route("/", methods=["POST", "GET"])
@app.route("/mcp", methods=["POST", "GET"])
def mcp_endpoint():
    if request.method == "GET":
        return jsonify({
            "name": "RVATF Mindset Connector",
            "version": VERSION,
            "description": "RVATF v2 — Risk-Validated Automated Trading Framework with corrected sizing, kill switch, and execution rules"
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
                "version": VERSION
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
