import os
import re
from urllib.parse import urlparse
from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from main import get_base_resume, parse_job_description, tailor_resume, generate_answer


from resume_builder import create_resume_pdf
import time

app = Flask(__name__)
CORS(app)  # Enable CORS for Chrome Extension

# Ensure generated_resumes directory exists
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESUME_DIR = os.path.join(BASE_DIR, 'generated_resumes')
os.makedirs(RESUME_DIR, exist_ok=True)

@app.route('/view/<path:filename>', methods=['GET'])
def view_resume(filename):
    """Serve the generated resume PDF."""
    """Serve the generated resume PDF."""
    return send_from_directory(RESUME_DIR, filename)

@app.route('/answer_question', methods=['POST'])
def answer_question():
    try:
        data = request.json
        if not data or 'question' not in data or 'jd_text' not in data:
            return jsonify({"error": "Missing question or jd_text"}), 400
            
        question = data['question']
        jd_text = data['jd_text']
        provider = data.get('provider', 'gemini')
        
        print(f"Generating answer for: {question} (Provider: {provider})")
        answer = generate_answer(question, jd_text, provider)
        
        return jsonify({"answer": answer})
    except Exception as e:
        print(f"Error answering question: {str(e)}")
        return jsonify({"error": str(e)}), 500

def extract_company_name(url):
    """Extract company name from URL (e.g., www.google.com -> google)."""
    if not url:
        return "Unknown_Company"
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        # Remove www. and .com/.org/etc
        if domain.startswith('www.'):
            domain = domain[4:]
        company = domain.split('.')[0]
        return company.capitalize()
    except:
        return "Unknown_Company"

@app.route('/generate', methods=['POST'])
def generate_resume():
    try:
        data = request.json
        if not data or 'jd_text' not in data:
            return jsonify({"error": "No job description text provided"}), 400
            
        jd_text = data['jd_text']
        job_url = data.get('url', '')
        # Provider can be 'gemini', 'ollama', or 'openrouter'
        provider = data.get('provider', 'gemini')
        
        # 1. Parse JD
        print(f"Parsing Job Description... (Provider: {provider})")
        jd_analysis = parse_job_description(jd_text, provider=provider)
        
        # 2. Tailor Resume
        print("Tailoring Resume...")
        base_resume = get_base_resume()
        tailored_resume = tailor_resume(base_resume, jd_analysis, provider=provider)
        
        # 3. Create Directory Structure
        company_name = extract_company_name(job_url)
        company_dir = os.path.join(RESUME_DIR, company_name)
        os.makedirs(company_dir, exist_ok=True)
        
        # 4. Generate PDF
        print(f"Generating PDF for {company_name}...")
        filename = "Pranay_Saggar_Resume.pdf"
        output_path = os.path.join(company_dir, filename)
            
        create_resume_pdf(tailored_resume, output_path)
        
        # 5. Return URL for preview
        # Construct local URL
        view_url = f"http://localhost:8000/view/{company_name}/{filename}"
        
        return jsonify({
            "status": "success",
            "view_url": view_url,
            "filename": filename
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    print("🚀 Starting Resume Generator Server on port 8000...")
    app.run(host='0.0.0.0', port=8000, debug=True)
