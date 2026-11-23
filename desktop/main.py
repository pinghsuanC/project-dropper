import requests

from app.desktop_client import DesktopClient


def main():
    try:
        DesktopClient().execute()
    except (requests.ConnectionError, requests.Timeout) as e:
        print(f"Server not reachable. Aborted. ({e.__class__.__name__})")
        print(f"{'=' * 75}\n")
    except requests.HTTPError as e:
        # only raised where you call raise_for_status()
        print(f"Server error {e.__class__.__name__}")
        print(f"{'=' * 75}\n")


if __name__ == "__main__":
    main()
