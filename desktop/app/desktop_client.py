import json
import time

import qrcode

from app.apis import file_apis, pairing_apis
from app.auth.device_auth_client import DeviceAuthClient
from app.helper import utility
from config import (
    CLOUDFLARE_SERVICE_TOKEN_CLIENT_ID_MOBILE,
    CLOUDFLARE_SERVICE_TOKEN_CLIENT_SECRET_MOBILE,
)


class DesktopClient:
    def __init__(self):
        # Run once on setting up, if need to change the key, delete the device_key.pem file to regenerate
        self.token = None
        self.paired_device = None

    def execute(self):
        self._print_divider(new_line=True)

        device_auth = DeviceAuthClient()
        self.token = device_auth.login()
        check_me = device_auth.login_session()

        self._print_message(new_line=False, msg=f"Welcome, {check_me['name']}")

        self.prompt_for_pairing_if_needed()

        self._print_divider(new_line=False)
        self.auto_download_files()

        self._print_message(new_line=False, msg="Finished")

    def auto_download_files(self):
        if self.paired_device is None or self.token is None:
            return

        print("□ Checking for files... Please don't interrupt the process.")
        file_apis.download_files(self.token)

    def prompt_for_pairing_if_needed(self):
        if self.token is None:
            print("Identity invalid.")
            return

        print("□ Check paired device...")
        self.paired_device = pairing_apis.get_paired_device(self.token)

        if self.paired_device is None:
            print("You are not paired with any device yet.")

            # Allow the phone into the server
            selection = input(
                "Enter 'y' and press Enter to send server config to your mobile... Please have your mobile ready. \n"
            )
            if selection == "y":
                self._start_connection()
            else:
                print("Omitted the server config sharing process.")
                return

            # Start pairing process
            selection = input("Enter 'y' and press Enter to start pairing process...\n")
            if selection == "y":
                self._start_pairing()
            else:
                print("Bye.")
        else:
            print(
                f"You have been paired with the following device since {utility.format_date(self.paired_device['paired_at'])}\n"
                f"  Device name: {self.paired_device['name']}\n"
                f"  Platform: {self.paired_device['platform']}"
            )

    def _start_connection(self):
        """Show a QR to send CF configurations over to phone to avoid storing configs in the apk."""
        if self.token is None:
            print("Identity invalid.")
            return

        try:
            self._print_config_qr()
            print("□ DO NOT SHARE THIS CODE WITH ANYONE □")
            print("□ The QR code will only be shown for 15s □")
            for remaining in range(15, 0, -1):
                print(
                    f"\rScan with your phone. Hiding in {remaining:2d}s ",
                    end="",
                    flush=True,
                )
                time.sleep(1)
        except KeyboardInterrupt:
            print("Connection cancelled.")
        finally:
            self._clear_screen()

    def _start_pairing(self) -> None:
        """Show a pairing QR and wait until a phone claims it. Returns the paired device, or None."""

        if self.token is None:
            print("Identity invalid.")
            return

        pairing_session = pairing_apis.start_pairing_request(self.token)

        self._print_pairing_qr(pairing_session["pairing_token"])
        print("Waiting on your mobile phone to claim code...")

        try:
            while time.time() < pairing_session["expires_at"]:
                data = pairing_apis.get_pairing_request(
                    self.token, pairing_session["pairing_request_id"]
                )
                if data["status"] == "accepted":
                    self.paired_device = pairing_apis.get_paired_device(self.token)
                    break
                time.sleep(2)
        except KeyboardInterrupt:
            print("Pairing cancelled.")
            return
        finally:
            # clear the scrren as the qr codes contain important information
            self._clear_screen()

        if not self.paired_device:
            print("Code expired. Run pairing again for a new one.")
        else:
            self._print_divider(new_line=True)
            print(f"Paired with {self.paired_device['name']} 🎉")

        return

    def _print_pairing_qr(self, pairing_token: str):
        payload = json.dumps(
            {
                "pairing_token": pairing_token,
            }
        )

        qr = qrcode.QRCode(border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        qr.print_ascii(invert=True)

    def _print_config_qr(self):
        payload = json.dumps(
            {
                "cloudflare_client_id": CLOUDFLARE_SERVICE_TOKEN_CLIENT_ID_MOBILE,
                "cloudflare_access_key": CLOUDFLARE_SERVICE_TOKEN_CLIENT_SECRET_MOBILE,
            }
        )

        qr = qrcode.QRCode(border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        qr.print_ascii(invert=True)

    def _clear_screen(self) -> None:
        print("\033[2J\033[3J\033[H", end="", flush=True)
        # subprocess.run("cls" if os.name == "nt" else "clear", shell=True, check=False)

    def _print_divider(self, new_line=False) -> None:
        print(f"{'\n' if new_line == True else ''}{'=' * 75}")

    def _print_message(self, new_line=False, msg: str = ""):
        msg_len = len(msg) + 2
        left = (75 - msg_len) // 2
        right = 75 - msg_len - left
        print(f"{'\n' if new_line == True else ''}{'=' * left} {msg} {'=' * right}")
