from app.auth.device_auth_client import DeviceAuthClient
from app.auth.device_session import DeviceSession


def main():
    # Run once on setting up, if need to change the key, delete the device_key.pem file to regenerate
    device_auth = DeviceAuthClient()
    token = device_auth.login()
    check_me = DeviceSession.check_device_session(token)
    print("Session info:", check_me)


# img = qrcode.make("the link you send to your phone")
# img.show()


if __name__ == "__main__":
    main()
