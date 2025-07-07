from flask import Flask, request, jsonify
import requests
from simple_salesforce import Salesforce

app = Flask(__name__)

# Salesforce credentials
SF_USERNAME = 'balaji.j@terralogic.com'
SF_PASSWORD = 'Balu@3303'
SF_SECURITY_TOKEN = 'lvq4mJ6Oi6a7aPv6arl8P70y3'
SF_DOMAIN = 'login'

# OCR API endpoint
OCR_API_URL = 'https://clickscanstg.terralogic.com/ocr/invoice/'

@app.route('/handle-invoice', methods=['POST'])
def handle_invoice():
    try:
        data = request.get_json()
        document_id = data.get('documentId')
        case_id = data.get('caseId')

        if not document_id or not case_id:
            return jsonify({'error': 'Missing documentId or caseId'}), 400

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
            return jsonify({'error': 'No file found for given documentId'}), 404

        version = result['records'][0]
        version_id = version['Id']
        filename = version['Title'] + '.' + version['FileExtension']
        print('[INFO] Retrieved ContentVersion:', version_id, filename)

        # Step 3: Download file from Salesforce
        file_url = f"{sf.base_url}sobjects/ContentVersion/{version_id}/VersionData"
        file_res = requests.get(file_url, headers={"Authorization": "Bearer " + sf.session_id})
        if file_res.status_code != 200:
            return jsonify({'error': 'Failed to download file from Salesforce'}), 500
        print('[INFO] Downloaded file from Salesforce')

        # Step 4: Send file to OCR API
        files = {
            'file': (filename, file_res.content, 'application/octet-stream')
        }
        ocr_res = requests.post(OCR_API_URL, files=files)
        print('[DEBUG] OCR API status code:', ocr_res.status_code)
        print('[DEBUG] Raw OCR response:', ocr_res.text)

        if ocr_res.status_code != 200:
            return jsonify({
                'error': 'OCR API failed',
                'statusCode': ocr_res.status_code,
                'response': ocr_res.text
            }), 502

        # Step 5: Parse OCR response
        ocr_json = ocr_res.json()
        print('[DEBUG] Raw OCR response:', ocr_json)
        
        parsed = ocr_json.get('parsedData', {})
        print('[DEBUG] Parsed OCR data:', parsed)
        
        if not parsed:
            print('[ERROR] OCR parsing failed or missing parsedData')
            return jsonify({
                'error': 'OCR response missing parsedData',
                'ocrRaw': ocr_json
            }), 500

        # Step 6: Extract and clean values
        merchant_name = parsed.get('merchant_name') or 'Unknown'
        currency = parsed.get('currency') or 'N/A'

        try:
            raw_total = parsed.get('total_amount', '0')
            total_amount = float(raw_total.replace(',', '').strip())
        except Exception as e:
            print('[ERROR] Failed to convert total_amount:', raw_total)
            total_amount = 0

        print('[INFO] Final parsed values - Merchant:', merchant_name,
              'Amount:', total_amount, 'Currency:', currency)

        # Step 7: Create Invoice__c record in Salesforce
        invoice_data = {
            'Merchant_Name__c': merchant_name,
            'Total_Amount__c': total_amount,
            'Currency__c': currency,
            'Case__c': case_id
        }
        print('[DEBUG] invoice_data:', invoice_data)

        invoice_res = sf.Invoice__c.create(invoice_data)
        print('[DEBUG] invoice_res:', invoice_res)

        if not invoice_res.get('success'):
            return jsonify({
                'error': 'Failed to create Invoice__c',
                'details': invoice_res
            }), 500

        return jsonify({
            'status': 'success',
            'ocrResult': parsed,
            'invoiceId': invoice_res.get('id')
        }), 200

    except Exception as e:
        print('[ERROR] Exception occurred:', str(e))
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
