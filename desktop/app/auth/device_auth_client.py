import requests

from app.apis import auth_apis
from app.auth.device_crypto import DeviceCrypto
from app.helper.device_helper import DeviceHelper
from exceptions import ApiError


class DeviceAuthClient:
    def __init__(self):
        # load or create on start up
        self.device_auth = DeviceCrypto()
        self.device_id = DeviceHelper.load_device_id()
        self.token = None  # TODO: expirations, automatic re-logins

        self._check_health()

    def _check_health(self) -> None:
        status = auth_apis.check_health()
        if status != "ok":
            raise ConnectionError

    def login(self) -> str:
        """Check current device registration. If not registered, register and update the local device id."""

        self.ensure_registered()

        try:
            return self._authenticate()
        except ApiError as e:
            print(e)
            return str(e)

    def ensure_registered(self) -> None:
        """Return the local device id, registering first if there isn't one."""
        if not self.device_id:
            try:
                self.device_id = auth_apis.register_device()
            except ApiError as e:
                if e.status == 409:
                    print(
                        "Already registered, please check the database if you have any issues."
                    )
                elif e.status == 400:
                    print("Server rejected the key:", e.detail)  # a bug on our side
                else:
                    print("Server error:", e)
            except requests.exceptions.ConnectionError:
                print("Can't reach the server.")
                return
        else:
            try:
                auth_apis.get_challenge()
            except ApiError as e:
                if e.status != 404:
                    raise
                print("Server doesn't know this device, registering again...")
                DeviceHelper.delete_device_id()
                self.device_id = auth_apis.register_device()
                return

    def _authenticate(self) -> str:
        if not self.device_id:
            raise AttributeError("Empty device id. Check your registration flow.")

        # ask for and return signature
        challenge = auth_apis.get_challenge()
        signature = self.device_auth.sign(challenge)
        self.token = auth_apis.verify_challenge(self.device_id, challenge, signature)
        return self.token

    def login_session(self) -> dict:
        if not self.token:
            # try to log in and get the token if not logged in yet
            self.token = self.login()

        if not self.token:
            raise AttributeError("Token is empty. Login first.")

        return auth_apis.get_current_device_session(self.token)

    def get_token(self) -> str | None:
        if not self.token:
            self.login_session()

        return self.token
