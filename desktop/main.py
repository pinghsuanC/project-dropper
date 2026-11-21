from app.clients import file_apis
from app.desktop_client import DesktopClient


def main():

    try:
        desktopClient = DesktopClient()
        desktopClient.execute()
    except Exception:
        print("Server not active. Aborted.")
        # print(e)
        print(f"{'=' * 66}\n")


# test_upload(token)
# file_apis.download_files(token)

# download file from receiver
# test_batch_upload(token)
# file_apis.download_files(token)


# img = qrcode.make("the link you send to your phone")
# img.show()


def test_batch_upload(token):
    file_apis.batch_upload(token, paths=["./test.txt", "./img.png"])


def test_upload(token):
    file_apis.upload_file(token, path="./test.txt")
    file_apis.upload_file(token, path="./img.png")


if __name__ == "__main__":
    main()
