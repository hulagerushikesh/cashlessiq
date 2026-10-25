"""Bound v3 request bodies before JSON parsing, including chunked requests."""

from fastapi import HTTPException


class WorkflowBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/v3/"):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        maximum = 2 * 1024**2 if headers.get(b"content-type") == b"application/pdf" else 512 * 1024
        total = 0

        async def bounded_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > maximum:
                raise HTTPException(413, "Request body exceeds the workflow limit")
            return message

        return await self.app(scope, bounded_receive, send)
