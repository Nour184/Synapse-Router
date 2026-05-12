import os
import sys
import json
import requests
import glob
import pymupdf4llm as pymu

# Note this sends directly to worker 1
INGEST_ENDPOINT = 'http://localhost:5000/api/ingest'

def extract_markdown_from_pdf(pdf_path: str) -> str:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Cannot find local PDF at: {pdf_path}")
    
    print(f"analyzing visual gemoetry and tables and text in '{os.path.basename(pdf_path)}'")
    md_text = pymu.to_markdown(pdf_path)

    if not md_text.strip():
        raise ValueError("Extracted Markdown is empty. Ensure the pdf contains readable text")
    
    print(f"Successfully extracted {len(md_text)} from '{os.path.basename(pdf_path)}'")
    return md_text

def ship_to_node(pdf_path: str):
    try:
        raw_markdown = extract_markdown_from_pdf(pdf_path)

        doc_id = os.path.splitext(os.path.basename(pdf_path))[0]

        payload = {
            "document_id": doc_id, 
            "text": raw_markdown
        }

        print(f"Transmitting '{doc_id}' payload to {INGEST_ENDPOINT}...")

        response = requests.post(
            INGEST_ENDPOINT, 
            json=payload, 
            headers={"Content-Type": "application/json"},
        )

        response.raise_for_status()

        result = response.json()
        print(f"\nSUCCESS: Document ingested safely in {result.get('processing_time', 'N/A')} seconds.")
        print(f"Server Message: {result.get('message')}")
            
    except requests.exceptions.ConnectionError:
        print("\nFATAL: Connection Refused. Is your NGINX gateway or Uvicorn container active?")

    except requests.exceptions.HTTPError as http_err:
        print(f"\nGATEWAY ERROR: Received HTTP {response.status_code} from server.")

        try:
            print(f"Detail: {response.json().get('detail', http_err)}")
        except json.JSONDecodeError:
            print(f"Raw Error Output: {response.text}")
    except Exception as e:
        print(f"\nINGESTION ABORTED: {e}")

if __name__ == "__main__":

    matches = glob.glob('./*.pdf')
    TARGET_PDF = matches[0] # pick the first match
 
    ship_to_node(TARGET_PDF)
