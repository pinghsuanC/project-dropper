import requests

from app.auth.device_auth import DeviceAuth
from app.clients import auth_apis
from app.helper.device_id_helper import DeviceIdHelper
from exceptions import ApiError


def main():
    # Run once on setting up, if need to change the key, delete the device_key.pem file to regenerate
    device_id = DeviceIdHelper.load_device_id()
    print(device_id)
    if not device_id:
        try:
            device_id = auth_apis.register_device()
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

    # ask for and return signature
    try:
        challenge = auth_apis.get_challenge()
        device_auth = DeviceAuth()
        signature = device_auth.sign(challenge)
        auth_apis.verify_challenge(device_id, challenge, signature)

    except ApiError as e:
        if e.status == 400:
            print("The signature has been rejected, process aborted.")

    # img = qrcode.make("the link you send to your phone")
    # img.show()


if __name__ == "__main__":
    main()
