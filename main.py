from fastapi import FastAPI, File, UploadFile, Form
import requests
import shutil
import os

app = FastAPI()

# ClickScan API base
CLICKSCAN_BASE = "https://clickscan.terralogic.com/client/api/v1"
DRAWER_ID = 1
TENANT_ID = "PrVDQYBqqV"
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJwYXlsb2FkIjp7ImlkIjoxLCJlbWFpbCI6InN1cGVyYWRtaW5AdGVycmFsb2dpYy5jb20iLCJ1c2VybmFtZSI6InN1cGVyYWRtaW4iLCJyb2xlcyI6WyJTQSJdfSwiaWF0IjoxNzU2NzkzMTY1LCJleHAiOjE3NTY4MzYzNjV9.aWLwlf_9PjV0S_g00uNyuKZqsrsWgPppwBVUBGNFM3Y"

headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "x-tenant-id": TENANT_ID
}


@app.get("/")
def root():
    return {"message": "FastAPI running on Render!"}


@app.post("/upload-to-batch/")
async def upload_to_batch(
    file: UploadFile = File(...),
    batch_name: str = Form("sample")
):
    """
    1. Create a batch (static drawer_id=1)
    2. Upload file to the created batch
    """

    # STEP 1: Create Batch
    batch_payload = {
        "name": batch_name,
        "drawer_id": DRAWER_ID
    }

    batch_resp = requests.post(
        f"{CLICKSCAN_BASE}/batch",
        headers=headers,
        json=batch_payload
    )

    if batch_resp.status_code != 200:
        return {"error": "Batch creation failed", "details": batch_resp.text}

    batch_data = batch_resp.json()["payload"][0]
    batch_id = batch_data["id"]

    # Save file temporarily
    temp_file_path = f"temp_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # STEP 2: Upload File to Batch
    files = {
        "file": (file.filename, open(temp_file_path, "rb"), file.content_type),
    }
    data = {"batch_id": str(batch_id)}

    upload_resp = requests.post(
        f"{CLICKSCAN_BASE}/batch_file/upload",
        headers=headers,
        files=files,
        data=data
    )

    # Cleanup temp file
    os.remove(temp_file_path)

    if upload_resp.status_code != 201:
        return {"error": "File upload failed", "details": upload_resp.text}

    return {
        "message": "File uploaded successfully",
        "batch_id": batch_id,
        "batch_name": batch_name,
        "clickscan_response": upload_resp.json()
    }
