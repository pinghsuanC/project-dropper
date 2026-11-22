from datetime import UTC, datetime

from exceptions import ApiError


def _check(response):
    if response.ok:
        return response.json()
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:  # body wasn't JSON (e.g. a crash page)
        detail = response.text
    raise ApiError(response.status_code, detail)


def format_date(unipox_time: int) -> str:
    """Transform a unipox time integer to displayable format."""
    date_time = datetime.fromtimestamp(unipox_time, tz=UTC).astimezone()
    return date_time.strftime("%Y-%m-%d %H:%M:%S")
