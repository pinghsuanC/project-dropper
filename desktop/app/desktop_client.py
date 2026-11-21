import json
import time
from datetime import UTC, datetime

import qrcode

from app.auth.device_auth_client import DeviceAuthClient
from app.clients import file_apis, pairing_apis


class DesktopClient:
    def __init__(self):
        # Run once on setting up, if need to change the key, delete the device_key.pem file to regenerate
        print(f"\n{'=' * 66}")
        # TODO: add check server. raise connection error if server is not active

        self.token = None
        self.paired_device = None

    def execute(self):
        device_auth = DeviceAuthClient()
        token = device_auth.login()
        check_me = device_auth.login_session()
        print(f":D Welcome, {check_me['name']}")

        self.token = token
        self.paired_device = None
        self.prompt_for_pairing_if_needed()
        self.auto_download_files()

    def auto_download_files(self):
        if self.paired_device is None or self.token is None:
            return

        print(f"{'=' * 66}")
        print("□ Checking for files... Please don't interrupt the process.")
        file_apis.download_files(self.token)
        print(f"{'=' * 30} Done {'=' * 30}\n")

    def prompt_for_pairing_if_needed(self):
        if self.token is None:
            print("Identity invalid.")
            return

        print("□ Check paired device...")
        self.paired_device = pairing_apis.get_paired_device(self.token)

        if self.paired_device is None:
            print("You are not paired with any device yet.")
            selection = input("Enter 'y' and press Enter to start pairing process...\n")
            if selection == "y":
                self._start_pairing()
            else:
                print("Bye.")
        else:
            paired_at_time = datetime.fromtimestamp(
                self.paired_device["paired_at"], tz=UTC
            ).astimezone()
            print(
                f"You are paired with the following device since {paired_at_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Device name: {self.paired_device['name']}\n"
                f"Platform: {self.paired_device['platform']}"
            )

    def _start_pairing(self) -> dict | None:
        """Show a pairing QR and wait until a phone claims it. Returns the paired device, or None."""

        if self.token is None:
            print("Identity invalid.")
            return

        pairing_session = pairing_apis.start_pairing_request(self.token)

        self._show_qr(pairing_session["pairing_token"])

        while time.time() < pairing_session["expires_at"]:
            data = pairing_apis.get_pairing_request(
                self.token, pairing_session["pairing_request_id"]
            )
            if data["status"] == "accepted":
                print(f"Paired with {data['paired_with']} 🎉")
                return data["paired_with"]
            time.sleep(2)

        print("Code expired. Run pairing again for a new one.")

        return None

    def _show_qr(self, pairing_token: str):
        payload = json.dumps(
            {
                "pairing_token": pairing_token,
            }
        )
        qr = qrcode.QRCode(border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
