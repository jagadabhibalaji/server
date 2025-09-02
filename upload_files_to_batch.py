from fastapi import FastAPI, UploadFile, Form
import requests

app = FastAPI()

CLICKSCAN_BASE_URL = "https://clickscan.terralogic.com/client/api/v1"
TENANT_ID = "PrVDQYBqqV" 
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJwYXlsb2FkIjp7ImlkIjozLCJlbWFpbCI6InNhbGVzQHRlcnJhbG9naWMuY29tIiwidXNlcm5hbWUiOiJTQUxFU1VTRVIiLCJyb2xlcyI6WyJBRE1JTiIsIkNMSUVOVCJdfSwiaWF0IjoxNzU2Nzk2MTU1LCJleHAiOjE3NTY4MzkzNTV9.o6MIuK7h_At_vSl_-8gKXFzm5L3pMGoGcvgs8GTV760"

HEADERS = {
    "x-tenant-id": TENANT_ID,
    "Authorization": f"Bearer {BEARER_TOKEN}"
}

@app.get("/")
def root():
    return {"message": "FastAPI middleware running on Render!"}


@app.post("/create-batch-and-upload")
async def create_batch_and_upload(batchName: str = Form(...), file: UploadFile = None):
    try:
        # ✅ Check file provided
        if not file:
            return {"error": "No file provided"}

        # 1️⃣ Create Batch
        create_resp = requests.post(
            f"{CLICKSCAN_BASE_URL}/batch",
            headers=HEADERS,
            json={"name": batchName}
        )
        create_resp.raise_for_status()
        batch_data = create_resp.json()

        if "payload" not in batch_data or len(batch_data["payload"]) == 0:
            return {"error": "Batch creation failed", "details": batch_data}

        batch_id = batch_data["payload"][0]["id"]

        # 2️⃣ Upload File to Batch
        files = {
            "file": (file.filename, await file.read(), file.content_type)
        }
        data = {"batch_id": str(batch_id)}

        upload_resp = requests.post(
            f"{CLICKSCAN_BASE_URL}/batch_file/upload",
            headers=HEADERS,
            files=files,
            data=data
        )
        upload_resp.raise_for_status()

        return {
            "message": "Batch created and file uploaded successfully",
            "batch": batch_data,
            "upload": upload_resp.json()
        }

    except Exception as e:
        return {"error": str(e)}
