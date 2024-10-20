import pdfplumber
import requests
from flask import Flask, request, jsonify
from supabase import create_client, Client

# Flask app
app = Flask(__name__)

# Supabase client initialization
SUPABASE_URL = "https://jzmjrzydykbdqklegzbe.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp6bWpyenlkeWtiZHFrbGVnemJlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjkwOTYyOTIsImV4cCI6MjA0NDY3MjI5Mn0.-vk8oK4ovtUUK2O_lPMwOeGqoTEuDVK6PHbd86GM9gQ"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Groq AI settings
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = "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"

# Function to extract text from PDF using pdfplumber
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

# Function to query Groq AI
def query_groq_ai(question, context=""):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    
    data = {
        "messages": [
            {
                "role": "system",
                "content": "You are HAUBot, a polite and graceful assistant. You will answer student queries regarding Holy Angel University. When the user says goodbye, you will reply 'Laus Deo Semper!'."
            },
            {
                "role": "user",
                "content": question
            }
        ],
        "model": "gemma2-9b-it",
        "temperature": 1,
        "max_tokens": 1024,
    }

    # If we have context from the handbook, add it
    if context:
        data["messages"].insert(1, {"role": "assistant", "content": context})

    response = requests.post(GROQ_API_URL, headers=headers, json=data)
    if response.status_code == 200:
        ai_response = response.json()["choices"][0]["message"]["content"]
        return ai_response
    else:
        return f"Error querying Groq AI. Status Code: {response.status_code}, Message: {response.text}"

# API route to scan the PDF document and query Groq API
@app.route("/scan", methods=["POST"])
def scan_document():
    data = request.json
    pdf_file_name = data.get("handbook")
    question = data.get("question")

    if not pdf_file_name or not question:
        return jsonify({"error": "PDF file name and question are required"}), 400

    if not download_pdf_from_supabase(pdf_file_name):
        return jsonify({"error": "Failed to download the PDF from Supabase."}), 500

    extracted_text = extract_text_from_pdf("downloaded_pdf.pdf")

    # Query Groq AI with the extracted text from the document as context
    ai_response = query_groq_ai(question, context=extracted_text)

    return jsonify({"ai_response": ai_response})

if __name__ == "__main__":
    app.run(debug=True)
