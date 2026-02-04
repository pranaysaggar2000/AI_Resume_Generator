import os
import re
from urllib.parse import urlparse
from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from main import get_base_resume, parse_job_description, tailor_resume, generate_answer, extract_text_from_pdf, extract_base_resume_info, analyze_resume_with_jd
import json


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
    """Serve the generated resume PDF. Handles nested paths."""
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
        # Use AI-extracted names if available, fallback to URL parsing
        ai_company = jd_analysis.get('company_name', 'Unknown_Company').replace(" ", "_").replace("/", "-")
        ai_job_id = jd_analysis.get('job_identifier', 'Job').replace(" ", "_").replace("/", "-")
        
        if ai_company == "Unknown_Company":
             ai_company = extract_company_name(job_url)
        
        # Structure: generated_resumes/{Company}/{Job_ID}/
        # E.g. generated_resumes/Google/Senior_Software_Engineer/
        company_dir = os.path.join(RESUME_DIR, ai_company, ai_job_id)
        os.makedirs(company_dir, exist_ok=True)
        
        # 4. Generate PDF
        print(f"Generating PDF for {ai_company} / {ai_job_id}...")
        safe_name = base_resume.get('name', 'Resume').replace(" ", "_")
        filename = f"{safe_name}_Resume.pdf"
        output_path = os.path.join(company_dir, filename)
            
        create_resume_pdf(tailored_resume, output_path)
        
        # 5. Return URL for preview
        # Construct local URL with nested path
        # Encode parts to ensure URL safety
        from urllib.parse import quote
        safe_company_url = quote(ai_company)
        safe_job_url = quote(ai_job_id)
        view_url = f"http://localhost:8000/view/{safe_company_url}/{safe_job_url}/{filename}"
        
        return jsonify({
            "status": "success",
            "view_url": view_url,
            "filename": filename,
            "resume_data": tailored_resume # Use this for analysis
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze_resume_endpoint():
    """Analyze the resume against JD."""
    try:
        data = request.json
        if not data or 'resume_data' not in data or 'jd_text' not in data:
            return jsonify({"error": "Missing resume_data or jd_text"}), 400
            
        resume_data = data['resume_data']
        jd_text = data['jd_text']
        
        # Call the analysis function
        analysis = analyze_resume_with_jd(resume_data, jd_text)
        
        return jsonify(analysis)
        
    except Exception as e:
        print(f"Error analyzing resume: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200

@app.route('/profile_status', methods=['GET'])
def profile_status():
    """Check if a user profile exists."""
    profile_path = os.path.join(BASE_DIR, 'user_profile.json')
    if os.path.exists(profile_path):
        try:
            with open(profile_path, 'r') as f:
                data = json.load(f)
                return jsonify({"exists": True, "name": data.get('name', 'User')})
        except:
            return jsonify({"exists": False})
    return jsonify({"exists": False})

@app.route('/regenerate_pdf', methods=['POST'])
def regenerate_pdf():
    """Regenerate PDF with manually edited data."""
    try:
        data = request.json
        if not data or 'resume_data' not in data:
            return jsonify({"error": "Missing resume_data"}), 400
            
        resume_data = data['resume_data']
        # optional: allow overriding filename or company
        filename = data.get('filename', 'Regenerated_Resume.pdf')
        company_name = data.get('company_name', 'Manual_Edit')
        
        # Create Directory Structure
        company_dir = os.path.join(RESUME_DIR, company_name)
        os.makedirs(company_dir, exist_ok=True)
        
        output_path = os.path.join(company_dir, filename)
        
        print(f"Regenerating PDF for {company_name} at {output_path}...")
        create_resume_pdf(resume_data, output_path)
        
        # Return new URL
        view_url = f"http://localhost:8000/view/{company_name}/{filename}"
        
        return jsonify({
            "status": "success",
            "view_url": view_url,
            "filename": filename
        })
        
    except Exception as e:
        print(f"Error regenerating PDF: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/upload_resume', methods=['POST'])
def upload_resume_endpoint():
    """Handle resume upload from extension."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    try:
        # Save temp file
        temp_path = os.path.join(BASE_DIR, "temp_upload.pdf")
        file.save(temp_path)
        
        # Open and extract
        with open(temp_path, "rb") as f:
            text = extract_text_from_pdf(f)
            
        if not text:
             return jsonify({"error": "Could not extract text from PDF"}), 400
             
        # Extract details with AI
        profile_data = extract_base_resume_info(text)
        
        if not profile_data or not profile_data.get("name"):
            return jsonify({"error": "Failed to extract profile data"}), 400
            
        # Save user_profile.json
        profile_path = os.path.join(BASE_DIR, 'user_profile.json')
        with open(profile_path, "w") as f:
            json.dump(profile_data, f, indent=4)
            
        # Clean up
        os.remove(temp_path)
        
        return jsonify({"status": "success", "name": profile_data.get("name")})
        
    except Exception as e:
        print(f"Error in upload: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Resume Generator Server on port 8000...")
    app.run(host='0.0.0.0', port=8000, debug=True)
