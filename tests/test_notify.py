import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from secretary import notify


def test_chunks_respect_limit_and_lines():
    text = "\n".join(f"line {i} " + "x" * 50 for i in range(100))
    parts = notify.chunks(text, limit=500)
    assert all(len(p) <= 500 for p in parts)
    assert "".join(parts) == text
    assert notify.chunks("y" * 1200, limit=500) == ["y" * 500, "y" * 500, "y" * 200]


def test_send_webhook_posts_mention_once(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/hook"
        notify.send_webhook(url, "a\n" * 1500, mention_user_id="123")
    finally:
        server.shutdown()
    assert len(received) == 2
    assert received[0]["content"].startswith("<@123> ")
    assert not received[1]["content"].startswith("<@123>")
    assert received[0]["allowed_mentions"] == {"users": ["123"]}
