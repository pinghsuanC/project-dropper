import requests

from app.auth.device_crypto import DeviceCrypto
from app.clients import auth_apis
from app.helper.device_helper import DeviceHelper
from exceptions import ApiError


class DeviceAuthClient:
    def __init__(self):
        # load or create on start up
        self.device_auth = DeviceCrypto()
        self.device_id = DeviceHelper.load_device_id()

    def login(self) -> str:
        """Check current device registration. If not registered, register and update the local device id."""

        self.ensure_registered()

        try:
            return self._authenticate()
        except ApiError as e:
            print(e)

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
                auth_apis.get_challenge(no_print=True)
            except ApiError as e:
                if e.status != 404:
                    raise
                print("Server doesn't know this device, registering again...")
                DeviceHelper.delete_device_id()
                self.device_id = auth_apis.register_device()
                return

    def _authenticate(self):
        # ask for and return signature
        challenge = auth_apis.get_challenge()
        signature = self.device_auth.sign(challenge)
        return auth_apis.verify_challenge(self.device_id, challenge, signature)
