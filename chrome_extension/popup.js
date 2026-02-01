document.addEventListener('DOMContentLoaded', function () {
    const generateBtn = document.getElementById('generateBtn');
    const statusDiv = document.getElementById('status');
    const errorDiv = document.getElementById('error');
    const successDiv = document.getElementById('success');

    const previewBtn = document.getElementById('previewBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const actionsDiv = document.getElementById('actions');
    const savePathSpan = document.getElementById('savePath');

    let currentViewUrl = '';

    // Restore State
    chrome.storage.local.get(['lastViewUrl', 'lastStatus', 'lastCompany'], (result) => {
        if (result.lastViewUrl) {
            currentViewUrl = result.lastViewUrl;
            actionsDiv.style.display = 'block';
            statusDiv.textContent = result.lastStatus || 'Restored previous session.';
            if (result.lastCompany) {
                savePathSpan.textContent = `generated_resumes/${result.lastCompany}/...`;
            }
        }
    });

    const setupUI = document.getElementById('setupUI');
    const mainUI = document.getElementById('mainUI');
    const uploadBtn = document.getElementById('uploadBtn');
    const resumeFile = document.getElementById('resumeFile');
    const profileNameSpan = document.getElementById('profileName');
    const updateProfileLink = document.getElementById('updateProfileLink');

    // Check Profile Status
    async function checkProfile() {
        try {
            const response = await fetch('http://localhost:8000/profile_status');
            const data = await response.json();

            if (data.exists) {
                setupUI.style.display = 'none';
                mainUI.style.display = 'block';
                profileNameSpan.textContent = data.name;
            } else {
                setupUI.style.display = 'block';
                mainUI.style.display = 'none';
            }
        } catch (e) {
            console.error("Server not running?", e);
            // Show main UI as fallback but with error
            errorDiv.textContent = "Could not connect to server. Is it running?";
            errorDiv.style.display = 'block';
            mainUI.style.display = 'block';
        }
    }

    // Initial Check
    checkProfile();

    // Update Profile Link
    updateProfileLink.addEventListener('click', (e) => {
        e.preventDefault();
        setupUI.style.display = 'block';
        mainUI.style.display = 'none';
    });

    // Upload Handler
    uploadBtn.addEventListener('click', async () => {
        if (!resumeFile.files.length) {
            alert("Please select a file.");
            return;
        }

        const file = resumeFile.files[0];
        const formData = new FormData();
        formData.append('file', file);

        uploadBtn.disabled = true;
        uploadBtn.textContent = "Uploading...";

        try {
            const response = await fetch('http://localhost:8000/upload_resume', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.status === 'success') {
                checkProfile(); // Refresh view
            } else {
                alert("Error: " + (data.error || "Unknown error"));
            }
        } catch (e) {
            alert("Upload failed: " + e.message);
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.textContent = "Upload Resume";
        }
    });

    // Preview Handler
    previewBtn.addEventListener('click', () => {
        if (currentViewUrl) {
            chrome.tabs.create({ url: currentViewUrl });
        }
    });

    // Download Handler
    downloadBtn.addEventListener('click', () => {
        if (currentViewUrl) {
            chrome.downloads.download({
                url: currentViewUrl,
                filename: 'Pranay_Saggar_Resume.pdf',
                saveAs: false
            });
        }
    });

    generateBtn.addEventListener('click', async () => {
        // Reset UI
        generateBtn.disabled = true;
        errorDiv.style.display = 'none';
        actionsDiv.style.display = 'none';
        statusDiv.textContent = 'Extracting page content...';

        try {
            // 1. Get current tab
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

            if (!tab) {
                throw new Error("Could not access current tab");
            }

            // 2. Execute script to get text
            const results = await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () => document.body.innerText
            });

            if (!results || !results[0] || !results[0].result) {
                throw new Error("Could not extract text from page");
            }

            const jdText = results[0].result;
            const jobUrl = tab.url;

            // Provider Selection
            const provider = document.getElementById('providerSelect').value;
            const providerNames = {
                'gemini': 'Gemini (Cloud)',
                'ollama': 'Ollama (Local)',
                'openrouter': 'OpenRouter (Cloud)'
            };

            // 3. Send to local server
            statusDiv.textContent = `Generating with ${providerNames[provider]}...`;

            const response = await fetch('http://localhost:8000/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    jd_text: jdText,
                    url: jobUrl,
                    provider: provider
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Server error: ${response.status}`);
            }

            // 4. Handle Success Response (JSON)
            const data = await response.json();

            if (data.status === 'success' && data.view_url) {
                currentViewUrl = data.view_url;
                const companyName = data.view_url.split('/')[4];

                // Show Actions
                statusDiv.textContent = 'Resume generated successfully!';
                actionsDiv.style.display = 'block';
                savePathSpan.textContent = `generated_resumes/${companyName}/...`;

                // Save State
                chrome.storage.local.set({
                    lastViewUrl: currentViewUrl,
                    lastStatus: 'Resume generated successfully!',
                    lastCompany: companyName
                });
            } else {
                throw new Error("Invalid server response");
            }

        } catch (err) {
            console.error(err);
            statusDiv.textContent = '';
            errorDiv.textContent = err.message || "An unknown error occurred";
            errorDiv.style.display = 'block';
        } finally {
            generateBtn.disabled = false;
        }
    });
    // Smart Q&A Handler
    const askBtn = document.getElementById('askBtn');
    const questionInput = document.getElementById('questionInput');
    const answerOutput = document.getElementById('answerOutput');

    askBtn.addEventListener('click', async () => {
        const question = questionInput.value.trim();
        if (!question) {
            alert('Please enter a question.');
            return;
        }

        askBtn.disabled = true;
        askBtn.textContent = 'Thinking...';
        answerOutput.style.display = 'none';
        answerOutput.textContent = '';
        errorDiv.style.display = 'none';

        try {
            // 1. Get current tab
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tab) throw new Error("Could not access current tab");

            // 2. Execute script to get text (JD context)
            const results = await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () => document.body.innerText
            });

            if (!results || !results[0] || !results[0].result) {
                throw new Error("Could not extract text from page");
            }
            const jdText = results[0].result;
            const provider = document.getElementById('providerSelect').value;

            // 3. Send to server
            const response = await fetch('http://localhost:8000/answer_question', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: question,
                    jd_text: jdText,
                    provider: provider
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Server error: ${response.status}`);
            }

            const data = await response.json();

            // 4. Show Answer
            answerOutput.textContent = data.answer;
            answerOutput.style.display = 'block';

        } catch (err) {
            console.error(err);
            errorDiv.textContent = err.message || "An error occurred";
            errorDiv.style.display = 'block';
        } finally {
            askBtn.disabled = false;
            askBtn.textContent = 'Ask Question';
        }
    });
});
