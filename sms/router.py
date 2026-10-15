"""Minimal path router with typed placeholders, e.g. /api/students/<int:sid>."""

import re

TOKEN = re.compile(r"<(?:(int):)?(\w+)>")


def compile_pattern(pattern):
    def replace(match):
        kind, name = match.group(1), match.group(2)
        return f"(?P<{name}>\\d+)" if kind == "int" else f"(?P<{name}>[^/]+)"

    return re.compile("^" + TOKEN.sub(replace, pattern) + "$")


class NoMatch(Exception):
    pass


class MethodNotAllowed(Exception):
    def __init__(self, allowed):
        self.allowed = allowed


class Router:
    def __init__(self):
        self.routes = []

    def add(self, method, pattern, handler, roles=(), public=False):
        self.routes.append(
            {
                "method": method.upper(),
                "regex": compile_pattern(pattern),
                "handler": handler,
                "roles": tuple(roles),
                "public": public,
            }
        )

    def resolve(self, method, path):
        method = method.upper()
        allowed = set()
        for route in self.routes:
            match = route["regex"].match(path)
            if not match:
                continue
            if route["method"] != method:
                allowed.add(route["method"])
                continue
            return route, match.groupdict()
        if allowed:
            raise MethodNotAllowed(sorted(allowed))
        raise NoMatch()
