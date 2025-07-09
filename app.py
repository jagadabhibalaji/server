from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import requests
from simple_salesforce import Salesforce
import re
from datetime import datetime
import uvicorn

app = FastAPI()

# Salesforce credentials
SF_USERNAME = 'balaji.j@terralogic.com'
SF_PASSWORD = 'Balu@3303'
SF_SECURITY_TOKEN = 'x81Rp7qI7Hz5bbv3qPPvr55M'
SF_DOMAIN = 'login'

# OCR API endpoint
OCR_API_URL = 'https://clickscanstg.terralogic.com/ocr/invoice/'

# Request body schema
class InvoiceRequest(BaseModel):
    documentId: str
    caseId: str

@app.post("/handle-invoice")
async def handle_invoice(data: InvoiceRequest):
    try:
        document_id = data.documentId
        case_id = data.caseId

        print('[INFO] Received request with documentId:', document_id, 'caseId:', case_id)

        # Step 1: Login to Salesforce
        sf = Salesforce(
            username=SF_USERNAME,
            password=SF_PASSWORD,
            security_token=SF_SECURITY_TOKEN,
            domain=SF_DOMAIN
        )
        print('[INFO] Logged into Salesforce')

        # Step 2: Get latest ContentVersion
        query = f"""
            SELECT Id, Title, FileExtension
            FROM ContentVersion
            WHERE ContentDocumentId = '{document_id}'
            ORDER BY CreatedDate DESC
            LIMIT 1
        """
        result = sf.query(query)
        if not result['records']:
            raise HTTPException(status_code=404, detail='No file found for given documentId')

        version = result['records'][0]
        version_id = version['Id']
        filename = version['Title'] + '.' + version['FileExtension']
        print('[INFO] Retrieved ContentVersion:', version_id, filename)

        # Step 3: Download file from Salesforce
        file_url = f"{sf.base_url}sobjects/ContentVersion/{version_id}/VersionData"
        file_res = requests.get(file_url, headers={"Authorization": "Bearer " + sf.session_id})
        if file_res.status_code != 200:
            raise HTTPException(status_code=500, detail='Failed to download file from Salesforce')
        print('[INFO] Downloaded file from Salesforce')

        # Step 4: Send file to OCR API
        files = {
            'file': (filename, file_res.content, 'application/octet-stream')
        }
        ocr_res = requests.post(OCR_API_URL, files=files)
        print('[DEBUG] OCR API status code:', ocr_res.status_code)
        print('[DEBUG] Raw OCR response:', ocr_res.text)

        if ocr_res.status_code != 200:
            raise HTTPException(status_code=502, detail='OCR API failed')

        ocr_json = ocr_res.json()
        parsed = ocr_json.get('parsedData', {})
        content = ocr_json.get('content', '')

        if not parsed:
            raise HTTPException(status_code=500, detail='OCR response missing parsedData')

        # Step 6: Clean fields
        merchant_name = parsed.get('merchant_name') or 'Unknown'
        currency = parsed.get('currency') or 'N/A'
        try:
            raw_total = parsed.get('total_amount', '0')
            total_amount = float(raw_total.replace(',', '').strip())
        except:
            total_amount = 0

        # Step 6.1: Extract expiry date
        expiry_date = None
        match = re.search(r'Expiry Date[:\-]?\s*(\d{2}/\d{2}/\d{4})', content, re.IGNORECASE)
        if match:
            try:
                expiry_date_obj = datetime.strptime(match.group(1), "%d/%m/%Y")
                expiry_date = expiry_date_obj.strftime("%Y-%m-%d")
            except:
                pass

        # Step 7: Create Invoice__c
        invoice_data = {
            'Merchant_Name__c': merchant_name,
            'Total_Amount__c': total_amount,
            'Currency__c': currency,
            'Case__c': case_id,
            'Expiry_Date__c': expiry_date if expiry_date else None
        }

        invoice_res = sf.Invoice__c.create(invoice_data)
        if not invoice_res.get('success'):
            raise HTTPException(status_code=500, detail='Failed to create Invoice__c')

        return {
            'status': 'success',
            'ocrResult': parsed,
            'invoiceId': invoice_res.get('id')
        }

    except Exception as e:
        print('[ERROR] Exception occurred:', str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Optional: for local run
if __name__ == '__main__':
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
