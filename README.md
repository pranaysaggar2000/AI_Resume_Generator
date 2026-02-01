# 🚀 AI Resume Generator & Tailor

An advanced, AI-powered tool that generates ATS-optimized resumes tailored to specific job descriptions. It features a Streamlit web app for manual use and a Chrome Extension for seamless integration with job boards.

## ✨ Key Features

-   **🎯 ATS Optimization**: Automatically tailors your resume keywords, summary, and bullet points to match the Job Description (JD) using advanced AI analysis.
-   **🤖 Multi-Model Support**:
    -   **Primary**: Google Gemini 1.5 Flash / 2.0 Flash.
    -   **Fallback**: Gemma 2 27B (via Gemini API).
    -   **Groq**: Ultra-fast inference with Llama 3 / Qwen.
    -   **Ollama**: Local model support.
    -   **OpenRouter**: Access to other models like Deepseek.
-   **📄 PDF Parsing with Link Extraction**: Extracts text and hidden hyperlinks (LinkedIn/Portfolio) from your existing PDF resume.
-   **🎨 Professional Layout**: Generates clean, polished PDFs using ReportLab with:
    -   Smart spacing adjustments (1pt precision).
    -   Overflow handling (smart trimming of optional bullets/projects).
    -   Clickable hyperlinks.
-   **🧩 Chrome Extension**: Tailor your resume directly from any job post page in your browser.
-   **💾 Persistence**: Saves your base profile (`user_profile.json`) so you don't need to re-upload every time.

## 🛠️ Prerequisites

-   Python 3.10+
-   API Keys for at least one provider (Google Gemini Recommended)

## 📦 Installation

1.  **Clone the repository** (or download the files).
2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

1.  **Create a `.env` file** in the project root.
2.  **Add your API keys**:
    ```env
    # Required for the default/best experience
    GEMINI_API_KEY=your_google_gemini_key

    # Optional: For ultra-fast inference
    GROQ_API_KEY=your_groq_key

    # Optional: For other models
    OPENROUTER_API_KEY=your_openrouter_key
    ```
3.  **Git Ignore**: `user_profile.json` and `.env` are automatically ignored to protect your data.

## 🚀 Usage

### Option 1: Web App (Streamlit)
Ideal for testing layout changes or manually pasting JDs.

1.  Run the app:
    ```bash
    streamlit run app.py
    ```
2.  Upload your existing PDF resume (first time only).
3.  Paste a Job Description.
4.  Click **Generate Tailored Resume**.

### Option 2: Chrome Extension (Recommended)
Tailor resumes directly while browsing job sites.

1.  **Start the Backend Server**:
    The extension needs a local server to handle the AI processing.
    ```bash
    python server.py
    ```
    *Keep this terminal window running.*

2.  **Load the Extension**:
    -   Open Chrome and go to `chrome://extensions/`.
    -   Enable **Developer mode** (top right).
    -   Click **Load unpacked**.
    -   Select the `chrome_extension` folder in this directory.

3.  **Use It**:
    -   Navigate to a job posting (e.g., LinkedIn, Greenhouse, Lever).
    -   Click the extension icon.
    -   If it's your first time, you'll be prompted to upload your base resume PDF.
    -   Click **Generate Resume**.
    -   The tailored PDF will be created in the `generated_resumes/` folder.

## 📂 Project Structure

-   `main.py`: Core logic for AI interaction, PDF parsing, and content tailoring.
-   `resume_builder.py`: PDF generation engine using ReportLab. Handles layout, fonts, and drawing.
-   `app.py`: Streamlit frontend interface.
-   `server.py`: Flask backend API for the Chrome Extension.
-   `user_profile.json`: Stores your parsed resume data (name, experience, skills) locally.
-   `chrome_extension/`: Source code for the browser extension (manifest, popup, scripts).
-   `requirements.txt`: Python dependencies.

## ❓ Troubleshooting

-   **Missing LinkedIn/Portfolio Links**: Make sure to re-upload your resume if you haven't recently. We added a fix to extract hidden hyperlinks from PDFs.
-   **Summary too short?**: We recently adjusted the prompt. If it's still short, check the logs in `main.py` to see the AI response.
-   **API Errors**: Check your `.env` file and ensure your API quota isn't exceeded. The system tries to fallback to Gemma 2 if Gemini fails.
