"""Manual UI fixture only: no model, database, project, or external-tool access.

Run with Python, then point a separate Vite preview at API port 8303.
POST /__test__/release releases the pending request with an explicit Mock error.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event

release = Event()
received_messages = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Cancelling the browser request is part of this fixture.

    def do_GET(self):
        if self.path == "/api/ai/models":
            return self.respond(200, {"provider": "codebuddycli", "available": True,
                "mode": "planned", "models": [{"id": "cli-default", "provider": "codebuddycli",
                    "label": "Mock UI · 无真实模型"}], "message": "仅用于界面测试，不会调用模型"})
        if self.path == "/api/ai/settings":
            return self.respond(200, {"provider": "codebuddycli", "model": "cli-default",
                "base_url": None, "api_key_configured": False,
                "api_protocol": "chat-completions", "streaming": True,
                "alignment_detail": "standard"})
        if self.path == "/api/ai/conversation":
            return self.respond(200, {"project_id": None, "messages": []})
        if self.path == "/__test__/received":
            return self.respond(200, {"messages": received_messages})
        return self.respond(404, {"message": "Mock UI fixture: route not provided"})

    def do_POST(self):
        if self.path == "/__test__/release":
            release.set()
            return self.respond(200, {"released": True})
        if self.path == "/api/ai/provider/models":
            return self.respond(200, {"provider": "codebuddycli", "mode": "planned",
                "models": [{"id": "cli-default", "provider": "codebuddycli",
                    "label": "Mock UI · 无真实模型"}], "message": "仅用于界面测试，不会探测模型"})
        if self.path == "/api/ai/provider/check":
            return self.respond(503, {"message": "Mock UI 不执行连接检查"})
        if self.path == "/api/ai/chat/stream":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            received_messages.append(body["message"])
            release.clear()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(b'data: {"type":"status","text":"Mock UI waiting"}\n\n')
                self.wfile.flush()
                release.wait(timeout=60)
                payload = json.dumps({"type": "error",
                    "text": "Mock UI：受控失败，未调用真实模型"}, ensure_ascii=False).encode()
                self.wfile.write(b"data: " + payload + b"\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if self.path != "/api/ai/chat":
            return self.respond(404, {"message": "Mock UI fixture: route not provided"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        received_messages.append(body["message"])
        release.clear()
        release.wait(timeout=60)
        return self.respond(503, {"message": "Mock UI：受控失败，未调用真实模型"})


if __name__ == "__main__":
    print("Mock UI-only API on 127.0.0.1:8303; no real AI", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8303), Handler).serve_forever()
