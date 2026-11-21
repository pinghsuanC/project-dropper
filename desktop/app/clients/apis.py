import os

import dotenv

dotenv.load_dotenv("../../.env")

_BASE_URL = os.getenv("API_BASE_URL")
