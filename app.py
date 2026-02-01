"""
Resume Generator Web UI
A Streamlit interface for generating ATS-optimized resumes from job descriptions.
"""

import os
import re
import time
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai

from resume_builder import create_resume_pdf
from main import get_base_resume, parse_job_description, tailor_resume

# Load environment variables
load_dotenv()

# Configure Gemini - using 1.5-flash for better quota availability
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")


def extract_company_name(jd_text: str, jd_analysis: dict) -> str:
    """
    Extract company name from the job description using Gemini.
    Returns a clean folder-safe name.
    """
    prompt = f"""
Extract ONLY the company name from this job description. Return just the company name, nothing else.
If you can't find a company name, return "Unknown_Company".

Job Description:
{jd_text[:2000]}

Company name:"""
    
    # Retry logic for rate limits
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            company = response.text.strip()
            
            # Clean the company name to be folder-safe
            company = re.sub(r'[<>:"/\\|?*]', '', company)  # Remove invalid chars
            company = company.replace(' ', '_')  # Replace spaces with underscores
            company = company[:50]  # Limit length
            
            if not company:
                company = "Unknown_Company"
                
            return company
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                st.warning(f"⏳ Rate limited. Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                st.warning(f"Could not extract company name: {e}")
                return "Unknown_Company"
    
    return "Unknown_Company"


def main():
    st.set_page_config(
        page_title="Resume Generator",
        page_icon="📄",
        layout="wide"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .stTextArea textarea {
        font-size: 14px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="main-header">📄 Resume Generator</h1>', unsafe_allow_html=True)
    st.markdown("**Generate ATS-optimized resumes tailored to any job description**")
    st.markdown("---")
    
    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        st.error("⚠️ GEMINI_API_KEY not found in environment. Please add it to your .env file.")
        st.code("GEMINI_API_KEY=your_api_key_here", language="bash")
        return
    
    # Two-column layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Paste Job Description")
        jd_text = st.text_area(
            "Job Description",
            height=400,
            placeholder="Paste the full job description here...\n\nInclude:\n- Job title\n- Company name\n- Location\n- Requirements\n- Responsibilities",
            label_visibility="collapsed"
        )
    
    with col2:
        st.subheader("⚙️ Settings")
        
        output_dir = st.text_input(
            "Output Directory",
            value="./generated_resumes",
            help="Base directory where resume folders will be created"
        )
        
        st.markdown("---")
        st.markdown("### 📋 Resume Preview")
        st.markdown("""
        **Name:** Pranay Saggar  
        **Skills:** Python, ML, LLMs, RAG, Docker, K8s  
        **Experience:** EazyML, Stealth Startup  
        """)
    
    st.markdown("---")
    
    # Generate button
    if st.button("🚀 Generate Tailored Resume", type="primary", use_container_width=True):
        if not jd_text.strip():
            st.error("Please paste a job description first!")
            return
        
        with st.spinner("🔍 Analyzing job description..."):
            try:
                # Parse JD
                jd_analysis = parse_job_description(jd_text)
                
                st.success(f"✅ Found: **{jd_analysis.get('job_title', 'N/A')}** at **{jd_analysis.get('location', 'N/A')}**")
                
                # Show keywords found
                keywords = jd_analysis.get('mandatory_keywords', [])
                if keywords:
                    st.info(f"🔑 Keywords: {', '.join(keywords[:10])}")
                
            except Exception as e:
                st.error(f"Error parsing JD: {e}")
                return
        
        with st.spinner("✨ Tailoring resume for ATS optimization..."):
            try:
                # Get base resume and tailor it
                base_resume = get_base_resume()
                tailored_resume = tailor_resume(base_resume, jd_analysis)
            except Exception as e:
                st.error(f"Error tailoring resume: {e}")
                return
        
        with st.spinner("📁 Extracting company name and creating folder..."):
            try:
                # Extract company name
                company_name = extract_company_name(jd_text, jd_analysis)
                
                # Create company folder
                company_dir = os.path.join(output_dir, company_name)
                os.makedirs(company_dir, exist_ok=True)
                
                # Set output path
                output_path = os.path.join(company_dir, "Pranay_Saggar_Resume.pdf")
                
            except Exception as e:
                st.error(f"Error creating folder: {e}")
                return
        
        with st.spinner("📄 Generating PDF..."):
            try:
                # Generate PDF
                create_resume_pdf(tailored_resume, output_path)
            except Exception as e:
                st.error(f"Error generating PDF: {e}")
                return
        
        # Success message
        st.markdown("---")
        st.success("🎉 Resume generated successfully!")
        
        st.markdown(f"""
        ### 📂 Output Details
        - **Company:** {company_name}
        - **Location:** `{os.path.abspath(output_path)}`
        - **Job Title:** {jd_analysis.get('job_title', 'N/A')}
        """)
        
        # Show the file path for easy access
        st.code(os.path.abspath(output_path), language="bash")
        
        # Offer to open folder
        st.markdown(f"📁 [Open folder in Finder](file://{os.path.abspath(company_dir)})")
        
        # Show what was tailored
        with st.expander("🔍 See tailoring details"):
            st.json(jd_analysis)


if __name__ == "__main__":
    main()
