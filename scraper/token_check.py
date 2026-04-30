import httpx


def is_token_valid(client) -> bool:
    try:
        client._make_request('GET', '/auth/profile')
        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return False
        raise
    except Exception:
        return False