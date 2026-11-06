# import qrcode

# # The data you want to encode (text or a URL)
# data = "Hellooooo"

# # Generate the QR code
# img = qrcode.make(data)

# # Save it as an image file
# img.save("simple_qr.png")


# Execute and print

import qrcode

from app.auth.device_auth import DeviceAuth
from app.auth.device_fingerprint_processor import DeviceFingerprintProcessor
from app.clients.apis import test, test2

# get pc fingerprint
device_fingerprint_processor = DeviceFingerprintProcessor()
device_fingerprint_processor.get_device_fingerprint()

# Run once on setting up, if need to change the key, delete the device_key.pem file to regenerate
device_auth = DeviceAuth()
public_key_pem = device_auth.get_public_key_pem()

img = qrcode.make(public_key_pem)
# img.show()

test2()
test()
