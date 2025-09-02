# app.py
from fastapi import FastAPI
from pydantic import BaseModel
import requests
import base64
import io
import os

app = FastAPI(title="ClickScan Middleware")

# ====== CONFIG - set these from env or replace directly (better: env) ======
CLICKSCAN_BASE = "https://clickscanstg.terralogic.com/client/api/v1"
TENANT_ID = os.getenv("CLICKSCAN_TENANT_ID", "PrVDQYBqqV")
BEARER_TOKEN = os.getenv("CLICKSCAN_BEARER_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJwYXlsb2FkIjp7ImlkIjozLCJlbWFpbCI6InNhbGVzQHRlcnJhbG9naWMuY29tIiwidXNlcm5hbWUiOiJTQUxFU1VTRVIiLCJyb2xlcyI6WyJBRE1JTiIsIkNMSUVOVCJdfSwiaWF0IjoxNzU2Nzk2MTU1LCJleHAiOjE3NTY4MzkzNTV9.o6MIuK7h_At_vSl_-8gKXFzm5L3pMGoGcvgs8GTV760")
# ==========================================================================

HEADERS = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "x-tenant-id": TENANT_ID
}

class FileItem(BaseModel):
    file_name: str
    file_base64: str
    content_type: str = "application/octet-stream"

class Payload(BaseModel):
    batch_name: str
    files: list[FileItem]


@app.post("/create-batch-and-upload")
def create_batch_and_upload(payload: Payload):
    """
    1) Create batch in ClickScan with drawer_id = 1
    2) Upload all files into the created batch in a multipart/form-data request
    """
    try:
        # 1) Create batch
        create_payload = {"name": payload.batch_name, "drawer_id": 1}
        resp = requests.post(f"{CLICKSCAN_BASE}/batch", headers=HEADERS, json=create_payload, timeout=60)

        if resp.status_code not in (200, 201):
            return {"status": "batch_create_failed", "status_code": resp.status_code, "body": resp.text}

        json_resp = resp.json()
        # defensive: get id from payload[0]
        batch_list = json_resp.get("payload", [])
        if not batch_list:
            return {"status": "batch_create_failed_no_payload", "body": json_resp}

        batch_id = batch_list[0].get("id")
        if not batch_id:
            return {"status": "batch_create_failed_no_id", "body": json_resp}

        # 2) Prepare multipart request for ClickScan batch_file/upload
        files_for_requests = []
        for f in payload.files:
            decoded = base64.b64decode(f.file_base64)
            # Each entry should be ('files[]', (filename, fileobj, content_type))
            files_for_requests.append(
                ("files[]", (f.file_name, io.BytesIO(decoded), f.content_type))
            )

        # additional form fields
        data = {
            "batch_id": str(batch_id),
            "order_no": "0",
            "location": "default"
        }

        upload_resp = requests.post(
            f"{CLICKSCAN_BASE}/batch_file/upload",
            headers={"x-tenant-id": TENANT_ID, "Authorization": f"Bearer {BEARER_TOKEN}"},  # requests will handle Content-Type for multipart
            files=files_for_requests,
            data=data,
            timeout=120
        )

        # Return ClickScan response and our batch id
        try:
            upload_json = upload_resp.json()
        except Exception:
            upload_json = {"raw_text": upload_resp.text}

        return {
            "status": "ok" if upload_resp.status_code in (200, 201) else "upload_failed",
            "clickscan_status_code": upload_resp.status_code,
            "clickscan_response": upload_json,
            "batch_id": batch_id,
            "batch_name": payload.batch_name
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
