import pdfplumber
import requests
from flask import Flask, request, jsonify
from supabase import create_client, Client
import time

app = Flask(__name__)

# Initialize Supabase client
SUPABASE_URL = "https://jzmjrzydykbdqklegzbe.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp6bWpyenlkeWtiZHFrbGVnemJlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjkwOTYyOTIsImV4cCI6MjA0NDY3MjI5Mn0.-vk8oK4ovtUUK2O_lPMwOeGqoTEuDVK6PHbd86GM9gQ"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Function to extract text using pdfplumber
def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# Groq AI settings
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = "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"

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

# Function to split text into chunks that respect the token limit
def split_text_into_chunks(text, chunk_size=1500):  # Keeping each chunk under the token limit
    words = text.split()
    for i in range(0, len(words), chunk_size):
        yield ' '.join(words[i:i + chunk_size])


def query_groq_ai(text):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    
    ai_responses = []
    for chunk in split_text_into_chunks(text):  # Send in chunks
        data = {
            "messages": [
                {"role": "user", "content": chunk}
            ],
            "model": "gemma2-9b-it",  # Adjust this to the model you're using
            "temperature": 1,
            "max_tokens": 1024,
        }

        while True:
            response = requests.post(GROQ_API_URL, headers=headers, json=data)

            if response.status_code == 200:
                ai_responses.append(response.json()["choices"][0]["message"]["content"])
                break
            elif response.status_code == 429:  # Rate limit exceeded
                # Extract retry wait time from response
                retry_after = float(response.json()["error"]["message"].split("in ")[-1].split("s")[0])
                print(f"Rate limit exceeded. Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                return f"Error querying Groq AI. Status Code: {response.status_code}, Message: {response.text}"

    # Return combined responses from the AI
    return ' '.join(ai_responses)




# API route to scan the PDF document, send to Groq AI, and return AI's response
@app.route("/scan", methods=["POST"])
def scan_document():
    data = request.json
    pdf_file_name = data.get("handbook")

    if not pdf_file_name:
        return jsonify({"error": "No PDF file name provided"}), 400

    # Download the PDF from Supabase
    if not download_pdf_from_supabase(pdf_file_name):
        return jsonify({"error": "Failed to download the PDF from Supabase."}), 500

    # Extract text from the PDF
    extracted_text = extract_text_from_pdf("downloaded_pdf.pdf")

    # Send the extracted text to Groq AI
    ai_response = query_groq_ai(extracted_text)

    return jsonify({"ai_response": ai_response})

if __name__ == "__main__":
    app.run(debug=True)
