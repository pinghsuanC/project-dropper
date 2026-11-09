import json
from pathlib import Path

DEVICE_FILE = Path(__file__).resolve().parent / "device.json"


class DeviceHelper:
    def __init__(self):
        pass

    @staticmethod
    def save_device_id(device_id: str) -> None:
        DEVICE_FILE.write_text(json.dumps({"device_id": device_id}))

    @staticmethod
    def load_device_id() -> str | None:
        print(DEVICE_FILE)
        if not DEVICE_FILE.exists():
            return None
        return json.loads(DEVICE_FILE.read_text())["device_id"]

    def delete_device_id() -> None:
        DEVICE_FILE.unlink(missing_ok=True)
