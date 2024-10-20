import pdfplumber
import requests
from flask import Flask, request, jsonify
from supabase import create_client, Client
import time
from celery import Celery

# Flask app
app = Flask(__name__)

# Celery configuration
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# Supabase client initialization
SUPABASE_URL = "https://jzmjrzydykbdqklegzbe.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp6bWpyenlkeWtiZHFrbGVnemJlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjkwOTYyOTIsImV4cCI6MjA0NDY3MjI5Mn0.-vk8oK4ovtUUK2O_lPMwOeGqoTEuDVK6PHbd86GM9gQ"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Groq AI settings
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = "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"

# Function to extract text using pdfplumber
def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# Function to download the PDF from Supabase
def download_pdf_from_supabase(pdf_file_name):
    try:
        # Download file from Supabase
        response = supabase.storage().from_("docu").download(pdf_file_name)
        with open("downloaded_pdf.pdf", "wb") as f:
            f.write(response)
        return True
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return False

# Function to split text into chunks
def split_text_into_chunks(text, chunk_size=1500):
    words = text.split()
    for i in range(0, len(words), chunk_size):
        yield ' '.join(words[i:i + chunk_size])

# Celery task for querying Groq AI
@celery.task
def query_groq_ai_task(text):
    print("Processing your query...")
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    
    ai_responses = []
    for chunk in split_text_into_chunks(text):
        data = {
            "messages": [{"role": "user", "content": chunk}],
            "model": "gemma2-9b-it",
            "temperature": 1,
            "max_tokens": 1024,
        }

        while True:
            response = requests.post(GROQ_API_URL, headers=headers, json=data)
            if response.status_code == 200:
                ai_responses.append(response.json()["choices"][0]["message"]["content"])
                break
            elif response.status_code == 429:
                retry_after = float(response.json()["error"]["message"].split("in ")[-1].split("s")[0])
                print(f"Rate limit exceeded. Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                return f"Error querying Groq AI. Status Code: {response.status_code}, Message: {response.text}"

    return ' '.join(ai_responses)

# API route to scan the PDF document
@app.route("/scan", methods=["POST"])
def scan_document():
    data = request.json
    pdf_file_name = data.get("handbook")

    if not pdf_file_name:
        return jsonify({"error": "No PDF file name provided"}), 400

    if not download_pdf_from_supabase(pdf_file_name):
        return jsonify({"error": "Failed to download the PDF from Supabase."}), 500

    extracted_text = extract_text_from_pdf("downloaded_pdf.pdf")

    # Asynchronously process the query
    task = query_groq_ai_task.delay(extracted_text)

    return jsonify({"task_id": task.id})

# Route to check task status
@app.route("/task_status/<task_id>")
def task_status(task_id):
    task = query_groq_ai_task.AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {"state": task.state}
    elif task.state != 'FAILURE':
        response = {"state": task.state, "result": task.result}
    else:
        response = {"state": task.state, "result": str(task.info)}
    
    return jsonify(response)

if __name__ == "__main__":
    app.run(debug=True)
