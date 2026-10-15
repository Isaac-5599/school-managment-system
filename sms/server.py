"""HTTP server: session handling, RBAC gate, static assets and API dispatch."""

import json
import os
import re
import sys
import threading
import traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import api, auth, db as db_module, router as router_module
from .http_util import ApiError, Response, json_response

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
COOKIE_NAME = "sms_session"
MAX_BODY = 1024 * 1024

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".json": "application/json; charset=utf-8",
}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}

CSP = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self'"

router = router_module.Router()
api.register(router)

# Seeding the demonstration database costs several seconds of password hashing, so
# the socket opens first and requests wait on this event instead of being refused.
READY = threading.Event()


class Context:
    def __init__(self, db, user, params, query, data, token):
        self.db = db
        self.user = user
        self.params = params
        self.query = query
        self.data = data or {}
        self.token = token
        self.set_cookie = None
        self.clear_cookie = False

    def get(self, name, default=None):
        values = self.query.get(name)
        if not values:
            return default
        return values[0]


def error(status, message):
    return ApiError(status, message)


class Handler(BaseHTTPRequestHandler):
    server_version = "SchoolMS/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # ---------------------------------------------------------------- plumbing
    def _send(self, response, extra_headers=None):
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        for key, value in response.headers.items():
            self.send_header(key, value)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(response.body)

    def _cookies(self):
        jar = SimpleCookie()
        raw = self.headers.get("Cookie")
        if raw:
            jar.load(raw)
        return jar

    def _raw_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise error(413, "Request body is too large")
        return self.rfile.read(length) if length else b""

    def _parse_json(self, raw):
        if not raw:
            return None
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if content_type and content_type != "application/json":
            raise error(415, "Requests with a body must use Content-Type: application/json")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise error(400, "Request body is not valid JSON")
        if not isinstance(parsed, dict):
            raise error(400, "Request body must be a JSON object")
        return parsed

    def _session_user(self, conn, token):
        session = auth.get_session(token)
        if not session:
            return None
        row = conn.execute(
            "SELECT id AS user_id, full_name, username, role, is_active FROM users WHERE id = ?",
            (session["user_id"],),
        ).fetchone()
        if not row or not row["is_active"]:
            auth.destroy_session(token)
            return None
        return dict(row)

    def _handle(self, method):
        parsed = urlparse(self.path)
        path = parsed.path

        if not path.startswith("/api/"):
            return self._serve_static(path, method)

        # Static assets answer immediately so a platform health check passes while
        # the first API call waits out database seeding.
        if not READY.wait(timeout=180):
            return self._send(Response('{"error":"Database is still being prepared."}', status=503),
                              {"Retry-After": "5"})

        conn = db_module.get_conn()
        try:
            raw = self._raw_body()
            try:
                route, params = router.resolve(method, path)
            except router_module.MethodNotAllowed as exc:
                return self._send(json_response({"error": "Method not allowed"}, 405),
                                  {"Allow": ", ".join(exc.allowed)})
            except router_module.NoMatch:
                return self._send(json_response({"error": "Not found"}, 404))

            token = self._cookies().get(COOKIE_NAME)
            token = token.value if token else None
            user = self._session_user(conn, token)

            if not route["public"] and not user:
                return self._send(json_response({"error": "Authentication required"}, 401))

            body = None
            if method in ("POST", "PUT", "PATCH", "DELETE"):
                body = self._parse_json(raw)

            query = parse_qs(parsed.query)
            ctx = Context(conn, user, params, query, body, token)
            result = route["handler"](ctx)

            if isinstance(result, Response):
                response = result
            else:
                response = json_response(result if result is not None else {"ok": True})

            if ctx.set_cookie:
                response.headers["Set-Cookie"] = (
                    f"{COOKIE_NAME}={ctx.set_cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age={auth.SESSION_TTL}"
                )
            if ctx.clear_cookie:
                response.headers["Set-Cookie"] = f"{COOKIE_NAME}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"

            conn.commit()
            return self._send(response)
        except ApiError as exc:
            conn.rollback()
            return self._send(json_response({"error": exc.message}, exc.status))
        except Exception as exc:  # noqa: BLE001 - never leak a traceback to the client
            conn.rollback()
            sys.stderr.write("ERROR %s %s: %r\n" % (method, path, exc))
            return self._send(json_response({"error": "Internal server error"}, 500))
        finally:
            conn.close()

    def _serve_static(self, path, method):
        if path == "/":
            path = "/index.html"
        safe = os.path.normpath(path).lstrip("/\\")
        target = os.path.normpath(os.path.join(WEB_DIR, safe))
        if not target.startswith(WEB_DIR + os.sep) or not os.path.isfile(target):
            target = os.path.join(WEB_DIR, "index.html")

        if not os.path.isfile(target):
            return self._send(json_response({"error": "web/index.html is missing"}, 500))

        extension = os.path.splitext(target)[1].lower()
        content_type = CONTENT_TYPES.get(extension, "application/octet-stream")
        with open(target, "rb") as handle:
            body = handle.read()

        headers = {"Cache-Control": "no-cache"}
        if content_type.startswith("text/html"):
            headers["Content-Security-Policy"] = CSP
        self._send(Response(body, content_type=content_type), headers)

    def do_GET(self):
        self._handle("GET")

    def do_HEAD(self):
        self._handle("HEAD")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def do_PATCH(self):
        self._handle("PATCH")


def _prepare_database():
    try:
        db_module.bootstrap().close()
    except Exception:
        traceback.print_exc()
    finally:
        READY.set()


def serve(host="127.0.0.1", port=8000):
    threading.Thread(target=_prepare_database, daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    print(f"School Management System running at http://{host}:{port}")
    print("Default administrator login -> username: admin  password: Admin@123")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.server_close()
