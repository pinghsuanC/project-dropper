from api_session import api
from app.helper.utility import _check
from config import API_BASE_URL


def start_pairing_request(token: str):
    """Create a pairing request, and retrieve pairing token"""

    headers = {"Authorization": f"Bearer {token}"}

    # ask for presigned upload url
    response = api.post(
        f"{API_BASE_URL}/pairing-request/start",
        headers=headers,
        timeout=5,
    )
    response = _check(response)
    data = response["data"]
    # print(response["message"])

    return data


def get_pairing_request(token: str, request_id: str):

    # ask for presigned upload url
    response = api.get(
        f"{API_BASE_URL}/pairing-request/{request_id}/get",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    response = _check(response)
    data = response["data"]
    # print(response["message"])

    return data


def get_paired_device(token: str) -> dict | None:
    response = api.get(
        f"{API_BASE_URL}/devices/paired",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    response = _check(response)
    data = response["data"]
    print(response["message"])

    return data["device"] if data["device"] else None


# TODO: enable websocket
# async def wait_for_pairing(token: str) -> dict | None:
#    if not API_BASE_URL:
#        return None
#
#    url = (
#        API_BASE_URL.replace("http", "ws", 1) + "/pairing-request/ws"
#    )  # http→ws, https→wss
#    async with websockets.connect(url) as ws:
#        await ws.send(json.dumps({"token": token}))
#        return json.loads(await ws.recv())  # blocks until the server pushes the result#
#
#    result = asyncio.run(wait_for_pairing(token))
