from app.clients import session_apis


class DeviceSession:
    def __init__():
        pass

    def check_device_session(token) -> dict:
        check_me = session_apis.get_current_device_session(token)
        return check_me
