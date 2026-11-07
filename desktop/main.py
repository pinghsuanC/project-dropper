# import qrcode

# # The data you want to encode (text or a URL)
# data = "Hellooooo"

# # Generate the QR code
# img = qrcode.make(data)

# # Save it as an image file
# img.save("simple_qr.png")


# Execute and print


import qrcode
import requests

from app.auth.device_fingerprint_processor import DeviceFingerprintProcessor
from app.clients.apis import register_device
from app.helper.device_helper import DeviceHelper
from exceptions import ApiError

DEVICE_TYPE = "desktop"

# get pc fingerprint
device_fingerprint_processor = DeviceFingerprintProcessor()
fingerprint = device_fingerprint_processor.get_device_fingerprint()

# Run once on setting up, if need to change the key, delete the device_key.pem file to regenerate
device_id = DeviceHelper.load_device_id()
if not device_id:
    try:
        data = register_device()
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


img = qrcode.make("the link you send to your phone")
# img.show()
