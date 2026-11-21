from exceptions import ApiError


def _check(response):
    if response.ok:
        return response.json()
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:  # body wasn't JSON (e.g. a crash page)
        detail = response.text
    raise ApiError(response.status_code, detail)
