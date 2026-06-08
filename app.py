import os
import json
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)

API_KEY = os.environ.get("RVATF_API_KEY", "change-me")

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


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def check_auth():
    key = request.headers.get("X-API-Key")
    return key == API_KEY


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "rvatf-mcp", "time": now_iso()})


@app.route("/tools", methods=["GET"])
def tools():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({
        "name": "RVATF MCP Connector",
        "mode": "read-only",
        "tools": [
            "health_check",
            "get_watchlist",
            "get_risk_rules",
            "get_backtest_summary",
            "get_live_positions",
            "get_trade_journal",
            "get_system_status"
        ]
    })


@app.route("/call", methods=["POST"])
def call():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True)
    tool = data.get("tool")
    args = data.get("arguments", {})

    if tool == "health_check":
        return jsonify({"ok": True, "time": now_iso()})

    if tool == "get_watchlist":
        enabled_only = args.get("enabled_only", False)
        items = [x for x in WATCHLIST if x["enabled"]] if enabled_only else WATCHLIST
        return jsonify({"count": len(items), "items": items, "time": now_iso()})

    if tool == "get_risk_rules":
        return jsonify({"rules": RISK_RULES, "time": now_iso()})

    if tool == "get_backtest_summary":
        strategy = args.get("strategy")
        result = BACKTESTS.get(strategy)
        if not result:
            return jsonify({"error": f"Unknown strategy: {strategy}"}), 400
        return jsonify({"summary": result, "time": now_iso()})

    if tool == "get_live_positions":
        return jsonify({"count": len(POSITIONS), "positions": POSITIONS, "time": now_iso()})

    if tool == "get_trade_journal":
        limit = int(args.get("limit", 20))
        return jsonify({"count": min(limit, len(JOURNAL)), "items": JOURNAL[:limit], "time": now_iso()})

    if tool == "get_system_status":
        return jsonify({
            "framework": "RVATF",
            "mode": "read-only",
            "kill_switch": True,
            "max_positions": 1,
            "time": now_iso()
        })

    return jsonify({"error": f"Unknown tool: {tool}"}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8787))
    app.run(host="0.0.0.0", port=port)
