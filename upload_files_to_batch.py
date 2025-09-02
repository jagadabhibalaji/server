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


# 1️⃣ Create batch only
@app.post("/create-batch")
def create_batch(batchName: str = Form(...)):
    create_resp = requests.post(
        f"{CLICKSCAN_BASE_URL}/batch",
        headers=HEADERS,
        json={"name": batchName}
    )
    create_resp.raise_for_status()
    return create_resp.json()


# 2️⃣ Upload file to existing batch
@app.post("/upload-file")
async def upload_file(batchId: str = Form(...), file: UploadFile = None):
    if not file:
        return {"error": "No file provided"}

    files = {
        "file": (file.filename, await file.read(), file.content_type)
    }
    data = {"batch_id": batchId}

    upload_resp = requests.post(
        f"{CLICKSCAN_BASE_URL}/batch_file/upload",
        headers=HEADERS,
        files=files,
        data=data
    )
    upload_resp.raise_for_status()
    return upload_resp.json()
