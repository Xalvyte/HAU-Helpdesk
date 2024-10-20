import pdfplumber
import requests
from flask import Flask, request, jsonify
from supabase import create_client, Client
import time

app = Flask(__name__)

# Supabase settings
SUPABASE_URL = "https://jzmjrzydykbdqklegzbe.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp6bWpyenlkeWtiZHFrbGVnemJlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjkwOTYyOTIsImV4cCI6MjA0NDY3MjI5Mn0.-vk8oK4ovtUUK2O_lPMwOeGqoTEuDVK6PHbd86GM9gQ"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Groq AI settings
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = "your-groq-api-key"

# Route for handling the Flutter request
@app.route('/scan', methods=['POST'])
def scan_document():
    data = request.json
    question = data.get('question')
    pdf_file_name = data.get('handbook')

    if not pdf_file_name:
        return jsonify({"error": "No PDF file name provided"}), 400

    # Download the PDF from Supabase
    if not download_pdf_from_supabase(pdf_file_name):
        return jsonify({"error": "Failed to download the PDF from Supabase."}), 500

    # Extract text from the PDF
    extracted_text = extract_text_from_pdf("downloaded_pdf.pdf")

    # Send the extracted text to Groq AI along with the user's question
    ai_response = query_groq_ai(extracted_text, question)

    return jsonify({"ai_response": ai_response})

# Function to download the PDF from Supabase
def download_pdf_from_supabase(pdf_file_name):
    try:
        response = supabase.storage().from_("docu").download(pdf_file_name)
        with open("downloaded_pdf.pdf", "wb") as f:
            f.write(response)
        return True
    except Exception as e:
        print(f"Error downloading PDF: {e}")
        return False

# Function to extract text using pdfplumber
def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# Function to query Groq AI
def query_groq_ai(text, question):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    
    data = {
        "messages": [
            {"role": "user", "content": question + "\n\n" + text}
        ],
        "model": "gemma2-9b-it",  # Adjust this to the model you're using
        "temperature": 1,
        "max_tokens": 1024,
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error querying Groq AI. Status Code: {response.status_code}, Message: {response.text}"

if __name__ == "__main__":
    app.run(debug=True)
