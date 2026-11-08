import os

import dotenv
import requests

dotenv.load_dotenv("../../.env")

_BASE_URL = os.getenv("API_BASE_URL")


def test():
    response = requests.get(f"{_BASE_URL}/")
    print(response.status_code, response.json())


def test2():

    response = requests.post(
        f"{_BASE_URL}/",
        json={"name": "widget", "price": 9.99},
        timeout=5,
    )
    print(response.status_code, response.json())
