import secrets

from fastapi.responses import JSONResponse


def authorized(request, key):
    return secrets.compare_digest(key.encode(), request.app.state.key.encode())


def error(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})
