import hmac
import subprocess

import dotenv

dotenv.load_dotenv()


class DeviceFingerprintProcessor:
    def __init__(self):
        pass

    def verify(self, received_hash: str) -> str:
        generated_hash = self.generate()
        return hmac.compare_digest(generated_hash, received_hash)

    def get_public(self) -> str:
        pass

    def get_device_fingerprint(self) -> str:
        device_info = self.get_device_info()

        concatenated_info = ""
        for code in [self.normalize(code) for code in device_info.values()]:
            concatenated_info += str(len(code)) + code

        # Create a SHA256 hash of the concatenated string
        # return hmac.new(
        #    os.environ.get("DEVICE_SHA256_KEY").encode(),
        #    concatenated_info.encode(),
        #    hashlib.sha256,
        # ).hexdigest()

        return concatenated_info

    def normalize(self, s: str) -> str:
        return s.strip().lower().replace("-", "").replace(" ", "")

    def get_device_info(self):
        # To ensure safety, get a few other system info
        cmds = {
            "uuid": [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_ComputerSystemProduct).UUID",
            ],
            "cpu_id": [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor).ProcessorId",
            ],
            "board_serial": [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_BaseBoard).SerialNumber",
            ],
            "disk_serial": [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_DiskDrive | Select-Object -First 1).SerialNumber",
            ],
        }
        results = {}

        for key, value in cmds.items():
            try:
                result = subprocess.run(
                    value, capture_output=True, text=True, check=True
                )
                results[key] = result.stdout.strip()
            except subprocess.CalledProcessError as e:
                print(f"Error executing PowerShell for {key}: {e}")

        return results
