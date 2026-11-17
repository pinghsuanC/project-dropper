import uuid

from fastapi import (
    APIRouter,
    HTTPException,
)
from fastapi.security import HTTPBearer

import repositories.file as file_repo
from auth import guards
from auth.dependencies import CurrentSession
from enums import FileStatus
from schemas.files import (
    FinishBatchUploadRequest,
    FinishDownloadRequest,
    FinishUploadRequest,
    PrepareBatchUploadRequest,
    PrepareUploadRequest,
    SentFilesResponse,
)
from storage.object_storage import ObjectStorage

router = APIRouter(prefix="/files", tags=["files"])
bearer = HTTPBearer()


@router.post("/prepare-batch-upload")
def prepare_batch_upload(
    body: PrepareBatchUploadRequest, deviceSession: CurrentSession
):
    """Prepare for uploads for a list of files."""

    if deviceSession is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    receiver_id = str(body.receiver_id)
    sender_device = guards.require_valid_session(deviceSession)
    receiver_device = guards.require_valid_device(receiver_id)

    obj_storage = ObjectStorage()
    prepared = []
    for f in body.files:
        file_id = str(uuid.uuid7())
        object_key = f"{receiver_id}/{file_id}"
        prepared.append(
            {
                **f,
                "id": file_id,
                "object_key": object_key,
                "upload_url": obj_storage.get_put_presigned_url(object_key),
                "status": FileStatus.PENDING,
            }
        )

    file_repo.insert_multiple_files(
        sender_device["id"], receiver_device["id"], prepared
    )

    return {
        "message": f"{len(prepared)} upload(s) prepared.",
        "data": {
            "files": [
                {
                    "file_id": p["id"],
                    "upload_url": p["upload_url"],
                    "client_ref": p["client_ref"],
                }
                for p in prepared
            ]
        },
    }


@router.post("/prepare-upload")
def prepare_upload(body: PrepareUploadRequest, deviceSession: CurrentSession):

    receiver_id = str(body.receiver_id)
    if deviceSession is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sender_device = guards.require_valid_session(deviceSession)
    receiver_device = guards.require_valid_device(receiver_id)

    file_id, object_key = file_repo.insert_file(
        sender_id=sender_device["id"],
        receiver_id=receiver_device["id"],
        file_name=body.file_name,
        size=body.size,
        content_type=body.content_type,
        checksum=body.checksum,
        status=FileStatus.PENDING,
    )

    obj_storage = ObjectStorage()
    upload_url = obj_storage.get_put_presigned_url(
        key=object_key,
    )

    return {
        "message": "Presigned url generated.",
        "data": {"upload_url": upload_url, "file_id": file_id},
    }


@router.post("/finish-batch-upload")
def finish_batch_upload(body: FinishBatchUploadRequest, session: CurrentSession):
    sender = guards.require_valid_session(session)
    file_ids = [str(i) for i in body.file_ids]

    files = file_repo.get_pending_files_for_sender(sender["id"], file_ids)
    if len(files) != len(file_ids):
        raise HTTPException(
            status_code=404, detail="Some files were not found or are not pending."
        )

    storage = ObjectStorage()
    for file in files:
        meta = storage.head_object(file["object_key"])
        if meta is None or meta["ContentLength"] != file["size"]:
            raise HTTPException(
                status_code=409, detail=f"Upload not found or incomplete: {file['id']}"
            )

    verified_ids = [f["id"] for f in files]
    file_repo.update_files_status(verified_ids, FileStatus.PENDING, FileStatus.UPLOADED)

    return {
        "message": f"{len(verified_ids)} file(s) uploaded.",
        "data": {"file_ids": verified_ids},
    }


@router.post("/finish-upload")
def finish_upload(body: FinishUploadRequest, deviceSession: CurrentSession):
    file_id = str(body.file_id)

    sender_device = guards.require_valid_session(deviceSession)

    file = file_repo.get_file_by_id(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found.")
    if file["sender_id"] != sender_device["id"]:
        raise HTTPException(status_code=403, detail="Unauthorized.")
    if file["status"] != FileStatus.PENDING:
        raise HTTPException(status_code=409, detail="File is not pending upload")

    # verify the object is uploaded
    meta = ObjectStorage().head_object(file["object_key"])  # None if missing
    if meta is None or meta["ContentLength"] != file["size"]:
        raise HTTPException(status_code=409, detail="Upload not found or incomplete")

    file_repo.update_file_status(file_id, FileStatus.UPLOADED)

    return {
        "message": "File uploaded successfully.",
        "data": {"file_id": file_id},
    }


@router.get("/check-pending-download")
def check_pending_download(deviceSession: CurrentSession):
    if deviceSession is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    receiver_device = guards.require_valid_session(deviceSession)

    files = file_repo.get_uploaded_files(receiver_id=receiver_device["id"])

    if not files:
        return {
            "message": "No pending files.",
            "data": {"files": []},
        }

    return {
        "message": "Found pending download files.",
        "data": {"files": files},
    }


@router.get("/sent", response_model=SentFilesResponse)
def get_sent_files(deviceSession: CurrentSession):
    """Files the caller sent that the receiver hasn't downloaded yet, newest first."""

    sender_device = guards.require_valid_session(deviceSession)
    files = file_repo.get_sent_files_waiting(sender_device["id"])

    return {
        "message": f"{len(files)} file(s) waiting.",
        "data": [
            {
                "file_id": f["id"],
                "file_name": f["file_name"],
                "size": f["size"],
                "status": f["status"],
                "receiver_name": f["receiver_name"],
                "created_at": f["created_at"],
            }
            for f in files
        ],
    }


@router.get("/prepare-download")
def prepare_download(deviceSession: CurrentSession):

    if deviceSession is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    receiver_device = guards.require_valid_session(deviceSession)
    files = file_repo.get_uploaded_files(receiver_id=receiver_device["id"])
    if not files:
        return {
            "message": "No files to download.",
            "data": {"file_objects": []},
        }

    obj_sto = ObjectStorage()
    file_objects = [
        to_pending_file_objects(f, obj_sto.get_get_presigned_url(f["object_key"]))
        for f in files
    ]

    return {
        "message": "Presigned url generated.",
        "data": {"file_objects": file_objects},
    }


@router.post("/finish-download")
def finish_download(body: FinishDownloadRequest, deviceSession: CurrentSession):

    receiver_device = guards.require_valid_session(deviceSession)

    file_ids = [str(id) for id in body.file_ids]

    files = file_repo.get_uploaded_files_for_receiver(receiver_device["id"], file_ids)
    if not files:
        raise HTTPException(status_code=404, detail="Files not found.")

    # okay if not all are found, they may be in other statuses, for example
    retrieved_ids = [f["id"] for f in files]
    downloaded_files = file_repo.update_files_status_for_receiver(
        receiver_id=receiver_device["id"],
        ids=retrieved_ids,
        original_status=FileStatus.UPLOADED,
        destination_status=FileStatus.DOWNLOADED,
    )

    # begin the process of downloads
    storage = ObjectStorage()
    failed_file_keys = storage.delete_objects(
        [f["object_key"] for f in downloaded_files]
    )

    deleted_file_ids = [
        f["id"] for f in downloaded_files if f["object_key"] not in failed_file_keys
    ]
    failed_deletion_ids = [
        f["id"] for f in downloaded_files if f["object_key"] in failed_file_keys
    ]

    file_repo.update_files_status_for_receiver(
        receiver_id=receiver_device["id"],
        ids=deleted_file_ids,
        original_status=FileStatus.DOWNLOADED,
        destination_status=FileStatus.DELETED,
    )

    message = f"{len(downloaded_files)} file(s) finished."
    if failed_deletion_ids:
        message += " Some files could not be removed from storage: " + ", ".join(
            failed_deletion_ids
        )

    return {
        "message": message,
        "data": {
            "finished": [f["id"] for f in downloaded_files],
            "failed_deletion_ids": failed_deletion_ids,
        },
    }


def to_pending_file_objects(f: dict, url: str) -> dict:
    return {
        "file_id": f["id"],
        "file_name": f["file_name"],
        "size": f["size"],
        "content_type": f["content_type"],
        "checksum": f["checksum"],
        "download_url": url,
    }
