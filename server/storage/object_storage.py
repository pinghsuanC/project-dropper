import os

import boto3
import dotenv
from botocore.exceptions import ClientError

dotenv.load_dotenv()


R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_BUCKET = os.getenv("R2_BUCKET")
R2_S3_API = os.getenv("R2_S3_API")
R2_API_TOKEN = os.getenv("R2_API_TOKEN")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCRESS_KEY = os.getenv("R2_SECRET_ACCRESS_KEY")


class ObjectStorage:
    def __init__(self):
        self.s3 = boto3.client(
            service_name="s3",
            endpoint_url=R2_S3_API,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCRESS_KEY,
            region_name="auto",
        )

    def head_object(self, object_key: str) -> dict | None:
        """Return the object's metadata, or None if it doesn't exist."""
        try:
            return self.s3.head_object(Bucket=R2_BUCKET, Key=object_key)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return None
            raise  # anything else (bad credentials, network) is a real error

    def get_delete_presigned_url(self, key: str, expires_in: int = 3600):
        return self.s3.generate_presigned_url(
            "delete_object",
            Params={"Bucket": R2_BUCKET, "Key": key},
            ExpiresIn=expires_in,  # Valid for 1 hour
        )

    def delete_object(self, object_key: str) -> None:
        self.s3.delete_object(Bucket=R2_BUCKET, Key=object_key)

    def delete_objects(self, object_keys: list[str]) -> None:
        if not object_keys:
            return
        response = self.s3.delete_objects(
            Bucket=R2_BUCKET,
            Delete={"Objects": [{"Key": k} for k in object_keys]},
        )
        return {err["Key"] for err in response.get("Errors", [])}

    def get_get_presigned_url(self, key: str, expires_in: int = 3600):
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET, "Key": key},
            ExpiresIn=expires_in,  # Valid for 1 hour
        )

    def get_put_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ):
        # Generate presigned URL for writing (PUT)
        return self.s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": R2_BUCKET,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )
