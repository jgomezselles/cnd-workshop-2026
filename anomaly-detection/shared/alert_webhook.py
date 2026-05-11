#!/usr/bin/env python3
"""Local Alertmanager webhook receiver for workshop demos.

It keeps recent alert notifications in memory and exposes them on a tiny local
web page, so participants can see alert delivery without configuring Slack,
email, or any external service.
"""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock


RECENT_ALERTS: deque[dict[str, object]] = deque(maxlen=100)
RECENT_ALERTS_LOCK = Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "cnd-alert-webhook/1.0"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"status": "ok"})
            return
        if self.path == "/alerts":
            self._send_json({"alerts": _recent_alerts()})
            return
        self._send_html(_render_html())

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {"raw": raw.decode("utf-8", errors="replace")}

        summary = _summarize(payload)
        with RECENT_ALERTS_LOCK:
            RECENT_ALERTS.appendleft(summary)

        print(json.dumps(summary, sort_keys=True), flush=True)
        self._send_json({"status": "received", "stored": len(_recent_alerts())})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def _send_json(self, body: dict[str, object]) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _summarize(payload: dict[str, object]) -> dict[str, object]:
    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        alerts = []

    return {
        "receivedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "receiver": payload.get("receiver"),
        "status": payload.get("status"),
        "groupLabels": payload.get("groupLabels"),
        "commonLabels": payload.get("commonLabels"),
        "alerts": [
            {
                "status": alert.get("status"),
                "labels": alert.get("labels"),
                "annotations": alert.get("annotations"),
            }
            for alert in alerts
            if isinstance(alert, dict)
        ],
    }


def _recent_alerts() -> list[dict[str, object]]:
    with RECENT_ALERTS_LOCK:
        return list(RECENT_ALERTS)


def _render_html() -> str:
    rows = []
    for idx, item in enumerate(_recent_alerts()):
        common_labels = item.get("commonLabels")
        group_labels = item.get("groupLabels")
        alerts = item.get("alerts")
        alert_count = len(alerts) if isinstance(alerts, list) else 0
        summary = _notification_title(item, group_labels, alert_count)
        open_attr = " open" if idx == 0 else ""
        rows.append(
            f"<details{open_attr}>"
            f"<summary>{escape(summary)}</summary>"
            "<div class='details-body'>"
            f"<p><strong>Receiver:</strong> {escape(str(item.get('receiver', '')))}</p>"
            f"<p><strong>Group:</strong> <code>{escape(json.dumps(group_labels, sort_keys=True))}</code></p>"
            f"<p><strong>Common:</strong> <code>{escape(json.dumps(common_labels, sort_keys=True))}</code></p>"
            f"<pre>{escape(json.dumps(alerts, indent=2, sort_keys=True))}</pre>"
            "</div>"
            "</details>"
        )

    if not rows:
        rows.append("<p class='empty'>No alerts received yet.</p>")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="10">
  <title>CND alert webhook</title>
  <style>
    body {{
      background: #111827;
      color: #e5e7eb;
      font: 16px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      padding: 32px;
    }}
    h1 {{ margin: 0 0 8px; }}
    .hint {{ color: #9ca3af; margin: 0 0 24px; }}
    main {{
      max-width: 1200px;
    }}
    details {{
      background: #1f2937;
      border: 1px solid #374151;
      border-radius: 8px;
      margin: 0 0 16px;
    }}
    summary {{
      cursor: pointer;
      font-size: 18px;
      font-weight: 650;
      list-style-position: inside;
      padding: 14px 16px;
    }}
    summary:hover {{ background: #273244; }}
    .details-body {{
      border-top: 1px solid #374151;
      padding: 16px;
    }}
    p {{
      margin: 0 0 10px;
    }}
    code {{
      background: #111827;
      border: 1px solid #374151;
      border-radius: 6px;
      display: block;
      margin-top: 4px;
      max-height: 120px;
      overflow: auto;
      padding: 8px;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    small {{ color: #9ca3af; font-weight: 400; }}
    pre {{
      background: #030712;
      border: 1px solid #374151;
      border-radius: 6px;
      max-height: 420px;
      overflow: auto;
      padding: 12px;
    }}
    .empty {{ color: #9ca3af; }}
    a {{ color: #93c5fd; }}
  </style>
</head>
<body>
  <main>
    <h1>CND alert webhook</h1>
    <p class="hint">Recent Alertmanager notifications. This page refreshes every 10 seconds. JSON: <a href="/alerts">/alerts</a></p>
    {''.join(rows)}
  </main>
</body>
</html>"""


def _notification_title(
    item: dict[str, object], group_labels: object, alert_count: int
) -> str:
    labels = group_labels if isinstance(group_labels, dict) else {}
    alertname = labels.get("alertname", "alert")
    service_name = labels.get("service_name", "unknown service")
    target = labels.get("for", "unknown signal")
    severity = labels.get("severity", "unknown severity")
    status = item.get("status", "unknown")
    received_at = item.get("receivedAt", "")
    return (
        f"{status} | {severity} | {alertname} | {service_name} / {target} "
        f"| {alert_count} alert(s) | {received_at}"
    )


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 5001), Handler)
    print("Alert webhook receiver listening on :5001", flush=True)
    server.serve_forever()
