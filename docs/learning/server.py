#!/usr/bin/env python3
"""Learning companion local server.

Usage:
    cd docs/learning && python server.py

Then open http://localhost:8765 in your browser.

Requirements:
    pip install anthropic  (already in QuantWorkstation venv)
"""

import json
import threading
import uuid
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn

import anthropic

PORT = 8765
DATA_FILE = Path(__file__).parent / "learning_log.json"
_file_lock = threading.Lock()

TOPICS = [
    # Gap topics — active study
    {"id": "11", "name": "#11 Risk & Factor Models",   "desc": "Fama-French, Barra, beta neutralization",          "gap": True},
    {"id": "12", "name": "#12 Portfolio Optimization", "desc": "Mean-variance, cvxpy, convex optimization",         "gap": True},
    {"id": "8",  "name": "#8 Statistical Arbitrage",   "desc": "Pairs trading, cointegration, stat arb",            "gap": True},
    {"id": "10", "name": "#10 Execution & Costs",      "desc": "Slippage, spread, transaction cost modeling",       "gap": True},
    {"id": "4",  "name": "#4 Model Weighting",         "desc": "Covariance, risk-parity, volatility-weighting",     "gap": True},
    {"id": "5",  "name": "#5 Portfolio Construction",  "desc": "Cross-sectional vs time-series models",             "gap": True},
    # Covered topics — built in QuantWorkstation
    {"id": "3",  "name": "#3 Strategy Evaluation",     "desc": "Sharpe, drawdown, alpha, beta, regressions",        "gap": False},
    {"id": "6",  "name": "#6 Backtesting",             "desc": "Walk-forward, dual-hurdle, OOS testing",            "gap": False},
    {"id": "13", "name": "#13 Live Trading Library",   "desc": "OMS, broker APIs, risk engine, live data feeds",    "gap": False},
    {"id": "7",  "name": "#7 Research Best Practices", "desc": "Overfitting, OOS, priors, model complexity",        "gap": False},
    {"id": "9",  "name": "#9 Course Project",          "desc": "Stat arb in crypto — full research workflow",       "gap": False},
    {"id": "1",  "name": "#1 The Big Picture",         "desc": "Backtesting, strategy types, quant firms overview", "gap": False},
    {"id": "2",  "name": "#2 Python & Libraries",      "desc": "Python, numpy, pandas, data analysis",              "gap": False},
]

SYSTEM_PROMPT = """You are the Learning Companion for Will, a full-stack SWE (JPMC SWE II) targeting quant developer/researcher roles.

Role: help Will master 6 gap topics through concise, practical explanations connected to his live trading platform (QuantWorkstation — algo trading with Neo4j research graph, ArcticDB data store, IBKR + Alpaca brokers, Sharpe >= 2.0 target, <= 4h holding, crypto + futures).

Full curriculum (13 topics):
GAP (active study, priority order): #11 Risk & Factor Models, #12 Portfolio Optimization, #8 Statistical Arbitrage, #10 Execution & Costs, #4 Model Weighting, #5 Portfolio Construction
COVERED (built in QuantWorkstation): #3 Strategy Evaluation, #6 Backtesting, #13 Live Trading Library, #7 Research Best Practices, #9 Course Project, #1 Big Picture, #2 Python

Depth scale: none -> awareness -> working -> applied.

Rules:
- Concise, specific — no preamble, no generic praise
- Connect theory to QuantWorkstation when concrete (e.g. "in your backtest harness, this maps to...")
- Cite specific sources: paper name + section, or book title + chapter
- Calibrate to learning log depth — skip basics Will already knows
- Surface connections between topics when relevant
- Under 200 words for definitions, under 400 for full explanations"""


def load_data() -> dict:
    with _file_lock:
        with open(DATA_FILE) as f:
            return json.load(f)


def save_data(data: dict) -> None:
    with _file_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)


def compute_streaks(sessions: list) -> dict:
    if not sessions:
        return {"current": 0, "longest": 0}

    dates = sorted({s["date"] for s in sessions})

    longest = 1
    run = 1
    for i in range(1, len(dates)):
        d1 = date.fromisoformat(dates[i - 1])
        d2 = date.fromisoformat(dates[i])
        if (d2 - d1).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1

    today = date.today()
    last = date.fromisoformat(dates[-1])
    gap = (today - last).days

    if gap > 1:
        current = 0
    else:
        current = 1
        for i in range(len(dates) - 2, -1, -1):
            d1 = date.fromisoformat(dates[i])
            d2 = date.fromisoformat(dates[i + 1])
            if (d2 - d1).days == 1:
                current += 1
            else:
                break

    return {"current": current, "longest": longest}


def build_context(data: dict) -> str:
    streaks = compute_streaks(data["sessions"])

    lines = [f"Learning log — {date.today().isoformat()}"]
    lines.append(f"Streak: {streaks['current']} day(s) current, {streaks['longest']} day(s) longest")
    lines.append("")
    lines.append("Topic depth:")
    for t in TOPICS:
        depth = data["topic_depth"].get(t["id"], "none")
        count = sum(1 for s in data["sessions"] if s["topic_id"] == t["id"])
        lines.append(f"  {t['name']}: {depth} ({count} session(s))")

    lines.append("")
    lines.append("Recent sessions (last 5):")
    recent = data["sessions"][-5:]
    if recent:
        for s in reversed(recent):
            note = f", notes: {s['notes']}" if s.get("notes") else ""
            lines.append(f"  {s['date']} — {s['topic_name']}, {s['duration_min']}min, depth: {s['depth_after']}{note}")
    else:
        lines.append("  None yet.")

    if data["recommendations"].get("next_reading"):
        lines.append("")
        lines.append(f"Last recommendation: {data['recommendations']['next_reading']}")

    return "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress noisy access log

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_file(Path(__file__).parent / "index.html", "text/html; charset=utf-8")
        elif self.path == "/api/data":
            data = load_data()
            data["streaks"] = compute_streaks(data["sessions"])
            data["topics"] = TOPICS
            self._json(data)
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/api/log":
            self._handle_log(body)
        elif self.path == "/api/chat":
            self._handle_chat(body)
        elif self.path == "/api/save-recommendation":
            self._handle_save_rec(body)
        elif self.path == "/api/resource-status":
            self._handle_resource_status(body)
        elif self.path == "/api/resource-url":
            self._handle_resource_url(body)
        else:
            self.send_error(404)

    def _handle_log(self, body: dict):
        data = load_data()
        session = {
            "id": str(uuid.uuid4())[:8],
            "date": date.today().isoformat(),
            "topic_id": body["topic_id"],
            "topic_name": next(t["name"] for t in TOPICS if t["id"] == body["topic_id"]),
            "duration_min": int(body["duration_min"]),
            "depth_after": body["depth_after"],
            "notes": body.get("notes", ""),
            "logged_at": datetime.now().isoformat(),
        }
        data["sessions"].append(session)
        data["topic_depth"][body["topic_id"]] = body["depth_after"]
        save_data(data)

        data["streaks"] = compute_streaks(data["sessions"])
        data["topics"] = TOPICS
        self._json(data)

    def _handle_resource_url(self, body: dict):
        data = load_data()
        if "resource_urls" not in data:
            data["resource_urls"] = {}
        if body.get("url"):
            data["resource_urls"][body["key"]] = body["url"]
        else:
            data["resource_urls"].pop(body["key"], None)  # empty string = clear override
        save_data(data)
        self._json({"ok": True})

    def _handle_resource_status(self, body: dict):
        data = load_data()
        if "resource_status" not in data:
            data["resource_status"] = {}
        data["resource_status"][body["key"]] = body["status"]
        save_data(data)
        self._json({"ok": True})

    def _handle_save_rec(self, body: dict):
        data = load_data()
        data["recommendations"]["next_reading"] = body["text"]
        data["recommendations"]["updated"] = date.today().isoformat()
        save_data(data)
        self._json({"ok": True})

    def _handle_chat(self, body: dict):
        message = body["message"]
        history = body.get("history", [])

        data = load_data()
        context = build_context(data)

        # Build messages — inject context as cached prefix on first user turn
        if not history:
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": message},
                ],
            }]
        else:
            first = history[0]
            if isinstance(first["content"], str):
                first_content = [
                    {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": first["content"]},
                ]
            else:
                first_content = [
                    {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
                    *first["content"],
                ]
            messages = (
                [{"role": first["role"], "content": first_content}]
                + history[1:]
                + [{"role": "user", "content": message}]
            )

        # Send SSE headers
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()

        client = anthropic.Anthropic()
        try:
            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=1024,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    chunk = json.dumps({"text": text})
                    self.wfile.write(f"data: {chunk}\n\n".encode())
                    self.wfile.flush()
        except BrokenPipeError:
            return
        except Exception as e:
            try:
                self.wfile.write(f"data: {json.dumps({'error': str(e)})}\n\n".encode())
                self.wfile.flush()
            except Exception:
                pass
        finally:
            try:
                self.wfile.write(b"data: {\"done\": true}\n\n")
                self.wfile.flush()
            except Exception:
                pass

    def _serve_file(self, path: Path, content_type: str):
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self._cors()
        self.end_headers()
        self.wfile.write(content)

    def _json(self, data: dict):
        content = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self._cors()
        self.end_headers()
        self.wfile.write(content)


class ThreadingServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    server = ThreadingServer(("localhost", PORT), Handler)
    print(f"http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
