"""
Automated Resume Generator
Tailors a resume based on a Job Description using Google Gemini API.
Optimized for ~95% ATS match score.
"""

import os
import json
import re
from dotenv import load_dotenv
import google.generativeai as genai
from resume_builder import create_resume_pdf


import requests

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")


# Model provider options
PROVIDERS = ["gemini", "ollama", "openrouter"]


def query_ollama(prompt: str, model_name: str = "llama3.1:8b") -> str:
    """Query local Ollama instance."""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False
            },
            timeout=300  # 5 minute timeout for reasoning models like deepseek-r1
        )
        if response.status_code == 200:
            return response.json().get('response', '')
        else:
            print(f"⚠️ Ollama Error: {response.status_code} - {response.text}")
            return ""
    except Exception as e:
        print(f"⚠️ Ollama Connection Error: {e}")
        return ""


def query_openrouter(prompt: str, model_name: str = "arcee-ai/trinity-large-preview:free") -> str:
    """Query OpenRouter API."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("⚠️ OPENROUTER_API_KEY not found in environment.")
        return ""
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://resume-generator.local",
                "X-Title": "Resume Generator",
            },
            json={
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            },
            timeout=300
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('choices', [{}])[0].get('message', {}).get('content', '')
        else:
            print(f"⚠️ OpenRouter Error: {response.status_code} - {response.text}")
            return ""
    except Exception as e:
        print(f"⚠️ OpenRouter Connection Error: {e}")
        return ""


def query_provider(prompt: str, provider: str = "gemini") -> str:
    """Query the specified AI provider."""
    if provider == "ollama":
        print("   Using Ollama (Local)...")
        return query_ollama(prompt)
    elif provider == "openrouter":
        print("   Using OpenRouter (Cloud)...")
        return query_openrouter(prompt)
    else:  # Default to gemini
        print("   Using Gemini (Cloud)...")
        response = model.generate_content(prompt)
        return response.text


def trim_projects_to_fit(resume_data: dict, max_bullets_initial: int = 3, min_bullets: int = 2, min_projects: int = 2) -> dict:
    """
    Initial project trimming. Strategy:
    1. Start with 3 bullets per project (LLM generates 5)
    2. Will be further trimmed by trim_projects_further if needed
    """
    if 'projects' not in resume_data or not resume_data['projects']:
        return resume_data
    
    projects = resume_data['projects']
    
    # Initially cap each project to max_bullets_initial (use top ranked)
    for proj in projects:
        if 'bullets' in proj and len(proj['bullets']) > max_bullets_initial:
            proj['bullets'] = proj['bullets'][:max_bullets_initial]
    
    return resume_data


def trim_projects_further(resume_data: dict, target_reduction: int, min_bullets: int = 2, min_projects: int = 2) -> dict:
    """
    Further trim projects to reduce height. Strategy:
    1. First reduce bullets per project (down to min_bullets=2)
    2. Then remove entire projects (down to min_projects=2)
    3. After removing a project, try to add bullets back to remaining projects
    """
    if 'projects' not in resume_data or not resume_data['projects']:
        return resume_data
    
    projects = resume_data['projects']
    # Store original bullets for potential restoration
    original_bullets = {i: proj.get('bullets', [])[:] for i, proj in enumerate(projects)}
    reduction_achieved = 0
    
    # Phase 1: Trim bullets from last project first (down to min_bullets)
    for i in range(len(projects) - 1, -1, -1):
        if reduction_achieved >= target_reduction:
            break
        
        proj = projects[i]
        bullets = proj.get('bullets', [])
        
        while len(bullets) > min_bullets and reduction_achieved < target_reduction:
            bullets.pop()  # Remove last (least important) bullet
            reduction_achieved += 14  # Approximate height per bullet
        
        proj['bullets'] = bullets
    
    # Phase 2: If still over, remove entire projects (keep at least min_projects)
    removed_project = False
    while len(projects) > min_projects and reduction_achieved < target_reduction:
        removed = projects.pop()  # Remove last project
        # Estimate height saved: header + bullets + spacer
        saved = 13 + len(removed.get('bullets', [])) * 14 + 2
        reduction_achieved += saved
        removed_project = True
        print(f"      Removed project: {removed.get('name', 'Unknown')}")
    
    # Phase 3: If we removed a project, try to add bullets back to remaining projects
    if removed_project and reduction_achieved > target_reduction:
        extra_space = reduction_achieved - target_reduction
        bullets_can_add = extra_space // 14
        
        # Try to restore bullets to remaining projects (most important project first)
        for i, proj in enumerate(projects):
            if bullets_can_add <= 0:
                break
            original = original_bullets.get(i, [])
            current = proj.get('bullets', [])
            
            # Add back bullets that were trimmed (if any)
            while len(current) < len(original) and bullets_can_add > 0:
                # Find next bullet to restore
                if len(current) < 3:  # Max 3 bullets per project
                    current.append(original[len(current)])
                    bullets_can_add -= 1
                else:
                    break
            
            proj['bullets'] = current
    
    resume_data['projects'] = projects
    return resume_data


def trim_skills_to_fit(resume_data: dict, max_lines: int = 6) -> dict:
    """
    Trim skills section. Each category can span up to 2 lines (~190 chars total).
    Skills are pre-ranked by JD relevance (most relevant first).
    """
    if 'skills' not in resume_data:
        return resume_data
    
    skills = resume_data['skills']
    num_categories = len(skills)
    
    if num_categories == 0:
        return resume_data
    
    # If we have more categories than max_lines, trim categories
    if num_categories > max_lines:
        keys = list(skills.keys())[:max_lines]
        resume_data['skills'] = {k: skills[k] for k in keys}
        skills = resume_data['skills']
    
    # Allow each category to span up to 2 lines (~190 chars)
    MAX_CHARS_PER_CATEGORY = 180  # ~2 lines at 10pt font
    
    for category, skill_str in skills.items():
        # Account for bullet point and category name
        prefix_len = len(f"• {category}: ")
        available_chars = MAX_CHARS_PER_CATEGORY - prefix_len
        
        skill_list = [s.strip() for s in skill_str.split(',')]
        trimmed_skills = []
        current_len = 0
        
        for skill in skill_list:
            skill_len = len(skill) + 2  # +2 for ", "
            if current_len + skill_len <= available_chars:
                trimmed_skills.append(skill)
                current_len += skill_len
            else:
                break  # Stop - we've filled 2 lines (remaining are least relevant)
        
        skills[category] = ', '.join(trimmed_skills)
    
    return resume_data


def get_base_resume() -> dict:
    """
    Returns the source-of-truth resume data based on Pranay Saggar's official resume.
    """
    return {
        "name": "Pranay Saggar",
        "contact": {
            "location": "San Francisco, CA",
            "phone": "+1 8572346569",
            "email": "pranaysaggar@gmail.com",
            "linkedin_url": "https://linkedin.com/in/pranay-saggar",
            "portfolio_url": "https://pranaysaggar.vercel.app/" # Retained from previous context
        },
        "summary": (
            "AI/ML Software Engineer & Researcher with 2+ years of experience architecting scalable "
            "Generative AI systems and MLOps pipelines. Expert in fine-tuning LLMs, building RAG architectures, "
            "and deploying high-availability models on AWS and GCP using Kubernetes and Docker. Proficient in "
            "the full ML lifecycle—from data engineering with Pandas and SQL to optimizing inference latency."
        ),
        "education": [
            {
                "institution": "Northeastern University (Khoury College of Computer Sciences)",
                "degree": "Master of Science, Computer Science",
                "gpa": "3.8/4.00",
                "dates": "Sep 2023 - Apr 2025",
                "location": "Boston, MA"
            },
            {
                "institution": "Guru Gobind Singh Indraprastha University",
                "degree": "Bachelor of Technology, Information Technology",
                "gpa": "8.97/10.00",
                "dates": "2018 - 2022",
                "location": "Delhi, India"
            }
        ],
        "skills": {
            "Languages & Core": "Python, SQL, Java, C++, Bash, Linux, Git, PostgreSQL, Snowflake, NoSQL",
            "Machine Learning & AI": (
                "PyTorch, TensorFlow, Scikit-learn, Pandas, NumPy, XGBoost, NLP & LLMs, RAG Pipelines, "
                "LangChain, HuggingFace, Time Series Forecasting"
            ),
            "Data Engineering & MLOps": (
                "AWS (EC2/S3), GCP (Vertex AI, Cloud Storage), Azure, Docker, Kubernetes, Jenkins, "
                "Terraform, Airflow, CI/CD, PowerBI, Ansible"
            ),
            "Web & Data": "FastAPI, REST APIs, React, Streamlit, Kafka, Spark, Tableau"
        },
        "experience": [
            {
                "company": "EazyML",
                "title": "Data Science Intern",
                "dates": "May 2024 - Aug 2024",
                "location": "San Francisco, CA",
                "bullets": [
                    "Developed multivariate Time Series forecasting models using Pandas and Scikit-learn.",
                    "Improved accuracy by 18% via lag features and exogenous inputs.",
                    "Automated pipelines by designing 5+ Airflow DAGs, cutting manual intervention by 60%."
                ]
            },
            {
                "company": "White Tree Devices",
                "title": "AI Engineer",
                "dates": "Jul 2021 - Jul 2023",
                "location": "Delhi, India",
                "bullets": [
                    "Architected a production-grade RAG pipeline using LangChain and Pinecone to enable semantic search over meeting transcripts, scaling to handle 500+ concurrent requests.",
                    "Optimized retrieval performance by implementing hybrid search and Redis caching, reducing query latency by 40%.",
                    "Developed high-concurrency microservices using FastAPI and Celery for asynchronous processing of audio transcripts.",
                    "Orchestrated containerized deployments on Kubernetes with Horizontal Pod Autoscaling (HPA) and Prometheus monitoring, ensuring 99.5% uptime."
                ]
            }
        ],
        "projects": [
            {
                "name": "Resumatrix",
                "dates": "Dec 2024 - Apr 2025",
                "bullets": [
                    "Developed a real-time SaaS application using FastAPI and Streamlit to score resumes, processing 100+ resumes per minute with <1s latency.",
                    "Integrated Pinecone and Google Gemini to engineer an intelligent parsing system using OpenAI embeddings for semantic matching."
                ]
            },
            {
                "name": "Agentic AI Chatbot Generator",
                "dates": "Apr 2025 - Present",
                "bullets": [
                    "Designed an Agentic AI system that autonomously scrapes content and deploys a Generative AI RAG-chatbot.",
                    "Orchestrated a multi-agent workflow using LangChain and LangGraph for data ingestion, text chunking, and FAISS vector store creation.",
                    "Automated deployment as a scalable API using Docker and FastAPI on GCP Cloud Run for one-click chatbot creation."
                ]
            },
            {
                "name": "Prediction and Classification of Student Academic Performance",
                "dates": "Jan 2022 - Jul 2022",
                "bullets": [
                    "Published in ADSAA Journal (ESCI indexed).",
                    "Achieved 92.27% accuracy using CatBoost with SMOTE analysis for balanced classification."
                ]
            }
        ],
        "leadership": [
            {
                "organization": "Northeastern University",
                "title": "Graduate Teaching Assistant",
                "dates": "Jan 2025 - Apr 2025",
                "location": "Boston, MA",
                "bullets": [
                    "Guided 100+ students by conducting labs, clearing doubts, and grading assignments, fostering a productive learning environment."
                ]
            }
        ]
    }


def parse_job_description(jd_text: str, provider: str = "gemini") -> dict:
    """
    Use AI provider to analyze the job description and extract key information.
    
    Args:
        jd_text: The job description text
        provider: One of 'gemini', 'ollama', or 'openrouter'
    
    Returns:
        dict with: location, job_title, keywords, action_verbs, skill_gaps
    """
    prompt = f"""
Analyze this job description and extract the following information. Return ONLY valid JSON.

Job Description:
{jd_text}

Extract and return this JSON structure:
{{
    "location": "City, State (extract ONLY the primary location, do not list multiple)",
    "job_title": "The exact job title from the posting",
    "mandatory_keywords": ["list", "of", "required", "technical", "skills"],
    "preferred_keywords": ["list", "of", "nice-to-have", "skills"],
    "soft_skills": ["communication", "leadership", "etc"],
    "action_verbs": ["developed", "implemented", "etc - verbs used in JD"],
    "industry_terms": ["domain-specific", "terminology"],
    "years_experience": "number or range if mentioned"
}}

Be thorough in extracting keywords - include all technologies, methodologies, and tools mentioned.
"""
    
    try:
        response_text = query_provider(prompt, provider)
        
        # Try to find JSON in the response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f"⚠️ API Error (Job Parsing): {e}")
        print("   Using default job description values.")

    # Fallback structure
    return {
        "location": "Remote",
        "job_title": "Data Scientist",
        "mandatory_keywords": [],
        "preferred_keywords": [],
        "soft_skills": [],
        "action_verbs": [],
        "industry_terms": [],
        "years_experience": ""
    }


def convert_markdown_to_html(text: str) -> str:
    """Convert markdown bold (**text**) to HTML bold (<b>text</b>)."""
    if not text:
        return text
    # Convert **text** to <b>text</b>
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    # Also handle any stray single asterisks
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
    return text


def clean_tailored_resume(resume_data: dict) -> dict:
    """Post-process the tailored resume to convert markdown to HTML."""
    
    # Clean summary
    if 'summary' in resume_data:
        resume_data['summary'] = convert_markdown_to_html(resume_data['summary'])
    
    # Clean skills
    if 'skills' in resume_data:
        for category in resume_data['skills']:
            resume_data['skills'][category] = convert_markdown_to_html(resume_data['skills'][category])
    
    # Clean experience bullets
    if 'experience' in resume_data:
        for exp in resume_data['experience']:
            if 'bullets' in exp:
                # Enforce max 3 bullets for Intern roles
                job_title = exp.get('title', exp.get('role', '')).lower()
                if 'intern' in job_title:
                    exp['bullets'] = exp['bullets'][:3]
                else:
                    # Enforce max 4 bullets for Full-time roles
                    exp['bullets'] = exp['bullets'][:4]
                
                exp['bullets'] = [convert_markdown_to_html(b) for b in exp['bullets']]
    
    # Clean project bullets
    if 'projects' in resume_data:
        for proj in resume_data['projects']:
            if 'bullets' in proj:
                proj['bullets'] = [convert_markdown_to_html(b) for b in proj['bullets']]
    
    # Clean leadership bullets
    if 'leadership' in resume_data:
        for lead in resume_data['leadership']:
            if 'bullets' in lead:
                lead['bullets'] = [convert_markdown_to_html(b) for b in lead['bullets']]
    
    return resume_data


def tailor_resume(base_resume: dict, jd_analysis: dict, provider: str = "gemini") -> dict:
    """
    Use AI provider to tailor the resume content for ATS optimization.
    Preserves all metrics and facts, only adjusts vocabulary.
    
    Args:
        base_resume: The base resume data
        jd_analysis: Analysis from parse_job_description
        provider: One of 'gemini', 'ollama', or 'openrouter'
    """
    prompt = f"""
You are a Strategic Resume Architect. Your PRIMARY GOAL is to achieve a 95+ ATS (Applicant Tracking System) match score.

TARGET JOB ANALYSIS:
{json.dumps(jd_analysis, indent=2)}

CURRENT RESUME DATA:
{json.dumps(base_resume, indent=2)}

CRITICAL OBJECTIVE: Rewrite the resume to MAXIMIZE ATS keyword matching while maintaining authenticity.

=== STRICT RULES ===

1. **Location**: Set contact.location to: "{jd_analysis.get('location', 'Remote')}"

2. **Summary** (2-3 sentences, under 50 words):
   - Mirror the exact job title from the JD
   - **CRITICAL:** Candidate is a **2025 New Grad** (Apr 2025). DO NOT change this to 2026.
   - Ignore JD graduation year requirements if they conflict with 2025.
   - Include 3-5 high-priority keywords from mandatory_keywords
   - End with a period

3. **Skills Section** (RANKED for trimming):
   - For EACH category, list skills as a comma-separated string
   - ORDER skills by JD relevance (most relevant FIRST)
   - Include 12-15 skills per category (extras will be trimmed to fit 2 lines)
   - Prioritize mandatory_keywords, then preferred_keywords

4. **Experience Bullets**:
   - Full-time roles: Generate EXACTLY 4 bullet points. Do not generate more.
   - Intern roles: Generate EXACTLY 3 bullet points. Do not generate more.
   - **CRITICAL: DO NOT SUMMARIZE OR SHORTEN.** Maintain the full depth and detail of the original bullets.
   - Each bullet should be SUBSTANTIVE (aim for ~2 lines per bullet).
   - Integrate JD keywords ONLY where they fit naturally. Do not force them.
   - PRESERVE all metrics exactly (18%, 60%, 99.5%, 40%, 30%, 92.27%, 2000, 5+)
   - **METRICS PRIORITY:** Emphasize system performance (throughput, latency, concurrency) over simple volume (user counts) where possible.
   - Each bullet = complete sentence ending with period (.)

5. **Project Bullets** (RANKED - generate 3 per project, use top 3):
   - For EACH project, generate exactly 5 bullet points ranked by importance
   - Top 3 bullets will be used (extras for trimming flexibility)
   - **Ensure detailed explanations** of technical implementation and impact.
   - Integrate keywords naturally
   - Each bullet = complete sentence ending with period (.)
   - Preserve all original metrics

6. **Formatting**:
   - Use <b>tags</b> for bold (NOT **asterisks**)
   - Bold ONLY the most significant metric or achievement in a bullet (Max 0-1 bold phrases per bullet).
   - DO NOT bold random keywords or technologies. Use bolding sparingly for impact.
   - Every bullet MUST end with a period (.)

7. **Tone & Style**:
   - Write in a PROFESSIONAL, NATURAL human voice.
   - Avoid "AI-like" or flowery language (e.g., instead of "Spearheaded the implementation...", use "Led the implementation..." or "Implemented...").
   - Sentences should be clear, direct, and fact-based.
   - When describing AI/ML projects for a generalist Software Engineer role, emphasize the engineering lifecycle (deployment, latency, APIs, Docker, testing) over the theoretical modeling, unless the JD specifically asks for model training.

8. **ATS Optimization**:
   - Use exact keyword matches from JD (not synonyms)
   - Include action verbs from the JD
   - Match industry terminology exactly

Return the complete resume as valid JSON with the same structure."""

    try:
        response_text = query_provider(prompt, provider)
        
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                tailored = json.loads(json_match.group())
                # Ensure we have all required fields
                if 'name' in tailored and 'contact' in tailored:
                    # Post-process to convert any remaining markdown to HTML
                    return clean_tailored_resume(tailored)
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f"⚠️ API Error (Tailoring): {e}")
        print("   Using base resume without AI tailoring.")

    # If parsing fails or API error, return base resume with just location updated (if valid)
    # If location detection also failed, it usually defaults to 'Remote' or 'N/A'
    if jd_analysis and 'location' in jd_analysis and jd_analysis['location'] not in ["Remote", "N/A"]:
         base_resume['contact']['location'] = jd_analysis['location']
         
    return base_resume


def generate_answer(question: str, jd_text: str, provider: str = "gemini") -> str:
    """
    Generate an answer to a user's question based on their resume and the job description.
    """
    base_resume = get_base_resume()
    
    prompt = f"""
You are a career coach and technical interviewer assisting the candidate during a job application or interview.

CANDIDATE PROFILE:
{json.dumps(base_resume, indent=2)}

JOB DESCRIPTION:
{jd_text}

USER QUESTION:
{question}

TASK:
Provide a concise, direct answer or talking point that the candidate can use.
- Connect their actual experience (from the profile) to the job requirements.
- Do NOT hallucinate experience they don't have.
- If the question is "Tell me about yourself", craft a short pitch relevant to this specific JD.
- If the question is technical, explain how they have used that technology based on their projects/work.
- Keep the tone professional and confident.
- Format with short paragraphs or bullet points for readability.
"""
    try:
        return query_provider(prompt, provider)
    except Exception as e:
        return f"Error generating answer: {str(e)}"


def generate_tailored_resume(jd_text: str, output_filename: str = "Tailored_Resume.pdf") -> str:
    """
    Main function to generate a tailored resume from a job description.
    
    Args:
        jd_text: The full job description text
        output_filename: Name of the output PDF file
        
    Returns:
        Path to the generated PDF
    """
    print("📄 Loading base resume...")
    base_resume = get_base_resume()
    
    print("🔍 Analyzing job description with Gemini...")
    jd_analysis = parse_job_description(jd_text)
    print(f"   📍 Location: {jd_analysis.get('location', 'N/A')}")
    print(f"   💼 Title: {jd_analysis.get('job_title', 'N/A')}")
    print(f"   🔑 Keywords found: {len(jd_analysis.get('mandatory_keywords', []))} mandatory, "
          f"{len(jd_analysis.get('preferred_keywords', []))} preferred")
    
    print("✨ Tailoring resume for ATS optimization...")
    tailored_resume = tailor_resume(base_resume, jd_analysis)
    
    print("📝 Generating PDF...")
    output_path = create_resume_pdf(tailored_resume, output_filename)
    
    print(f"✅ Resume generated: {output_path}")
    return output_path


def main():
    """CLI entry point - accepts job description input."""
    print("=" * 60)
    print("  AUTOMATED RESUME GENERATOR - ATS Optimized")
    print("=" * 60)
    print()
    
    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY not found in environment.")
        print("   Please create a .env file with your API key.")
        print("   See .env.example for the format.")
        return
    
    print("Paste the Job Description below.")
    print("When done, enter an empty line followed by 'END' on a new line:")
    print("-" * 60)
    
    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        except EOFError:
            break
    
    jd_text = '\n'.join(lines)
    
    if not jd_text.strip():
        print("❌ No job description provided. Exiting.")
        return
    
    print()
    print("-" * 60)
    
    # Generate the tailored resume
    output_file = generate_tailored_resume(jd_text)
    
    print()
    print("=" * 60)
    print(f"  Resume saved to: {output_file}")
    print("  Next steps:")
    print("    1. Review the PDF to ensure accuracy")
    print("    2. Test ATS score at jobscan.co or resumeworded.com")
    print("=" * 60)


if __name__ == "__main__":
    main()
