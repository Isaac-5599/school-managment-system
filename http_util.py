"""Shared response/error types for the HTTP layer."""


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Response:
    def __init__(self, body=b"", status=200, content_type="application/json; charset=utf-8", headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.body = body
        self.status = status
        self.content_type = content_type
        self.headers = headers or {}


def json_response(payload, status=200):
    import json

    return Response(json.dumps(payload), status=status)


def csv_response(text, filename):
    return Response(
        text,
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
