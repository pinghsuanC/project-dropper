from app.auth.device_auth_client import DeviceAuthClient
from app.auth.device_session import DeviceSession
from app.clients import file_apis


def main():
    # Run once on setting up, if need to change the key, delete the device_key.pem file to regenerate
    device_auth = DeviceAuthClient()
    token = device_auth.login()
    check_me = DeviceSession.check_device_session(token)
    print("Session info:", check_me)

    # test_upload(token)
    # file_apis.download_files(token)

    # download file from receiver
    # test_batch_upload(token)
    test_download(token)


# img = qrcode.make("the link you send to your phone")
# img.show()


def test_batch_upload(token):
    file_apis.batch_upload(token, paths=["./test.txt", "./img.png"])


def test_upload(token):
    file_apis.upload_file(token, path="./test.txt")
    file_apis.upload_file(token, path="./img.png")


def test_download(token):
    file_apis.download_files(token)


if __name__ == "__main__":
    main()
