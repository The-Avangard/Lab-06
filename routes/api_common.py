from flask import jsonify, request


MAX_SQLITE_ID = (1 << 63) - 1


def _is_v2_request():
    """Return True when the current request uses the v2 URL prefix."""
    return request.path.startswith('/api/v2/')


def api_response(data=None, status=200, message=None):
    """Create a successful API response for the requested API version.

    Version 1 returns the data directly. Version 2 wraps it in an object that
    includes the version and data fields.
    """
    if _is_v2_request():
        body = {'version': 'v2', 'data': data}
        if message:
            body['message'] = message
    else:
        body = data if data is not None else {}
        if message:
            body = {'message': message}

    return jsonify(body), status


def api_error(message, status=400, details=None):
    """Create a consistent JSON error response for either API version."""
    error = {'message': message}
    if details:
        error['details'] = details

    if _is_v2_request():
        body = {'version': 'v2', 'error': error}
    else:
        body = {'error': message}
        if details:
            body['details'] = details

    return jsonify(body), status
