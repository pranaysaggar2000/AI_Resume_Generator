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
    chrome.storage.local.get(['lastViewUrl', 'lastStatus', 'lastCompany', 'lastJobContext'], (result) => {
        if (result.lastViewUrl) {
            currentViewUrl = result.lastViewUrl;
            actionsDiv.style.display = 'block';
            statusDiv.textContent = result.lastStatus || 'Restored previous session.';
            if (result.lastCompany) {
                savePathSpan.textContent = `generated_resumes/${result.lastCompany}/...`;
            }
            if (result.lastJobContext) {
                const jobContextDiv = document.getElementById('jobContext');
                jobContextDiv.style.display = 'block';
                jobContextDiv.innerHTML = `Active Job: <strong>${result.lastJobContext}</strong>`;
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
            let shortUrl = "current page";
            try {
                const urlObj = new URL(jobUrl);
                shortUrl = urlObj.origin; // e.g. https://www.linkedin.com
            } catch (e) {
                console.log("Could not parse URL");
            }

            // Update Context UI immediately
            const jobContextDiv = document.getElementById('jobContext');
            jobContextDiv.style.display = 'block';
            jobContextDiv.innerHTML = `Active Job: <strong>${shortUrl}</strong>`;

            statusDiv.innerHTML = `Generating for <strong>${shortUrl}</strong><br>with ${providerNames[provider]}...`;

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
                const parts = data.view_url.split('/');
                // view_url is http://localhost:8000/view/Company/Job/Filename
                // parts: [http:, "", localhost:8000, view, Company, Job, Filename]
                const companyName = parts[4];
                const jobId = parts[5];

                // Show Actions
                statusDiv.textContent = 'Resume generated successfully!';
                actionsDiv.style.display = 'block';
                savePathSpan.textContent = `generated_resumes/${decodeURIComponent(companyName)}/${decodeURIComponent(jobId)}/...`;

                // Store data for analysis
                chrome.storage.local.set({
                    lastViewUrl: currentViewUrl,
                    lastStatus: 'Resume generated successfully!',
                    lastCompany: companyName,
                    lastResumeData: data.resume_data,
                    lastJdText: jdText,
                    lastJobContext: shortUrl // Save the context!
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

    // Analyze Handler
    const analyzeBtn = document.getElementById('analyzeBtn');
    const analysisResults = document.getElementById('analysisResults');
    const atsScoreDiv = document.getElementById('atsScore');
    const analysisDetailsDiv = document.getElementById('analysisDetails');

    analyzeBtn.addEventListener('click', async () => {
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = "Analyzing...";
        analysisResults.style.display = 'none';

        try {
            // Retrieve stored data
            const result = await chrome.storage.local.get(['lastResumeData', 'lastJdText']);
            if (!result.lastResumeData || !result.lastJdText) {
                throw new Error("Missing resume data. Please regenerate the resume first.");
            }

            const response = await fetch('http://localhost:8000/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    resume_data: result.lastResumeData,
                    jd_text: result.lastJdText
                })
            });

            if (!response.ok) {
                throw new Error("Analysis failed: " + response.statusText);
            }

            const analysis = await response.json();

            if (analysis.error) {
                throw new Error(analysis.error);
            }

            // Render Results
            atsScoreDiv.textContent = analysis.score || "N/A";

            let html = "";

            if (analysis.missing_keywords && analysis.missing_keywords.length > 0) {
                html += `<div style="margin-bottom: 8px;"><strong>⚠️ Missing Keywords:</strong><br>
                <span style="color: #d63384;">${analysis.missing_keywords.join(', ')}</span></div>`;
            }

            if (analysis.matching_areas && analysis.matching_areas.length > 0) {
                html += `<div style="margin-bottom: 8px;"><strong>✅ Strong Matches:</strong><br>
                 <span style="color: #198754;">${analysis.matching_areas.join(', ')}</span></div>`;
            }

            if (analysis.recommendations && analysis.recommendations.length > 0) {
                html += `<div><strong>💡 Recommendations:</strong>
                <ul style="margin: 5px 0; padding-left: 15px;">
                    ${analysis.recommendations.map(r => `<li>${r}</li>`).join('')}
                </ul></div>`;
            }

            analysisDetailsDiv.innerHTML = html;
            analysisResults.style.display = 'block';


        } catch (err) {
            console.error(err);
            alert("Analysis Error: " + err.message);
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = "📊 Analyze ATS Score";
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

    // --- ADVANCED EDITOR LOGIC ---
    const editBtn = document.getElementById('editBtn');
    const editorUI = document.getElementById('editorUI');
    const sectionSelect = document.getElementById('sectionSelect');
    const formContainer = document.getElementById('formContainer');
    const saveRegenBtn = document.getElementById('saveRegenBtn');
    const cancelEditBtn = document.getElementById('cancelEditBtn');

    let currentEditingData = null; // Local copy for editing
    let previousSection = null; // Track previous section for auto-saving

    editBtn.addEventListener('click', async () => {
        // Load data if not already loaded
        if (!currentEditingData) {
            const result = await chrome.storage.local.get(['lastResumeData']);
            if (result.lastResumeData) {
                currentEditingData = JSON.parse(JSON.stringify(result.lastResumeData)); // Deep copy
            } else {
                alert("No resume data found to edit.");
                return;
            }
        }

        // Show Editor
        editorUI.style.display = 'block';
        actionsDiv.style.display = 'none'; // Hide actions while editing

        // Trigger initial population
        sectionSelect.dispatchEvent(new Event('change'));

        // Also Initialize Tracker on Open
        // We need to re-fetch the pointer to currentEditingData or similar
        // But simpler: just set the tracker when the dropdown change event fires or here

        // Wait for data load (the original handler does this)
        setTimeout(() => {
            previousSection = sectionSelect.value;
        }, 100);
    });

    cancelEditBtn.addEventListener('click', () => {
        editorUI.style.display = 'none';
        actionsDiv.style.display = 'block';
    });

    // Helper: Render Inputs based on Section
    function renderEditor(section, data) {
        if (!formContainer) return;
        formContainer.innerHTML = ''; // Clear

        // 1. SUMMARY
        if (section === 'summary') {
            const div = document.createElement('div');
            div.className = 'edit-field';
            div.innerHTML = `<label>Summary Text</label>
                             <textarea id="edit_summary_text" style="height: 100px;">${data || ''}</textarea>`;
            formContainer.appendChild(div);

            // 2. CONTACT INFO
        } else if (section === 'contact') {
            // Handle raw string case just in case
            if (typeof data !== 'object') data = { location: data || "" };

            // Match keys expected by resume_builder.py
            const fields = [
                { key: 'location', label: 'Location' },
                { key: 'email', label: 'Email' },
                { key: 'phone', label: 'Phone' },
                { key: 'linkedin_url', label: 'LinkedIn URL' },
                { key: 'portfolio_url', label: 'Portfolio URL' },
                { key: 'github', label: 'GitHub' }
            ];

            fields.forEach(f => {
                // Try strict key match first, then fallback to partial (e.g. 'linkedin' for 'linkedin_url')
                let val = data[f.key];
                if (!val && f.key === 'linkedin_url') val = data['linkedin'];
                if (!val && f.key === 'portfolio_url') val = data['portfolio'];

                val = val || '';

                const div = document.createElement('div');
                div.className = 'edit-field';
                div.innerHTML = `<label>${f.label}</label>
                                  <input type="text" data-key="${f.key}" class="contact-input" value="${val}" placeholder="${f.label}">`;
                formContainer.appendChild(div);
            });

            // 3. SKILLS
        } else if (section === 'skills') {
            // Data is dict: { Category: "skill, skill", ... }
            if (!data) data = {};

            // Container for categories
            const listDiv = document.createElement('div');
            listDiv.id = 'skillsList';

            for (const [category, skills] of Object.entries(data)) {
                const div = document.createElement('div');
                div.className = 'item-block';
                div.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                        <input type="text" class="skill-category-input" value="${category}" style="font-weight: bold; width: 60%;" placeholder="Category Name">
                        <button class="remove-btn remove-category-btn">🗑️ Remove</button>
                    </div>
                    <textarea class="skill-values-input" style="height: 60px;">${skills}</textarea>
                 `;
                listDiv.appendChild(div);
            }
            formContainer.appendChild(listDiv);

            // Add Category Button
            const addBtn = document.createElement('button');
            addBtn.textContent = "➕ Add Skill Category";
            addBtn.style.cssText = "width: 100%; padding: 8px; background: #e9ecef; border: 1px dashed #ccc; color: #333; cursor: pointer; margin-top: 10px;";
            addBtn.onclick = () => {
                const div = document.createElement('div');
                div.className = 'item-block';
                div.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                        <input type="text" class="skill-category-input" value="New Category" style="font-weight: bold; width: 60%;">
                        <button class="remove-btn remove-category-btn">🗑️ Remove</button>
                    </div>
                    <textarea class="skill-values-input" style="height: 60px;"></textarea>
                `;
                listDiv.appendChild(div);
            };
            formContainer.appendChild(addBtn);

            // Delegate events for removal
            formContainer.addEventListener('click', (e) => {
                if (e.target.classList.contains('remove-category-btn')) {
                    e.target.closest('.item-block').remove();
                }
            });

            // 4. EXPERIENCE, PROJECTS & LEADERSHIP
        } else if (section === 'experience' || section === 'projects' || section === 'leadership') {
            // Data is List of Objects
            if (!data) data = [];

            const listDiv = document.createElement('div');
            listDiv.id = 'itemsList';

            data.forEach((item, index) => {
                renderItemBlock(listDiv, item, section);
            });
            formContainer.appendChild(listDiv);

            // Add Item Button
            let btnLabel = 'Item';
            if (section === 'experience') btnLabel = 'Job';
            if (section === 'projects') btnLabel = 'Project';
            if (section === 'leadership') btnLabel = 'Role';

            const addBtn = document.createElement('button');
            addBtn.textContent = `➕ Add ${btnLabel}`;
            addBtn.style.cssText = "width: 100%; padding: 8px; background: #e9ecef; border: 1px dashed #ccc; color: #333; cursor: pointer; margin-top: 10px;";

            addBtn.onclick = () => {
                // Template for new item
                let newItem = { bullets: ["New bullet"] };
                if (section === 'experience') {
                    newItem = { company: "New Company", role: "Role", location: "Location", dates: "Present", bullets: ["New bullet"] };
                } else if (section === 'projects') {
                    newItem = { name: "New Project", tech: "Tech Stack", dates: "2024", bullets: ["New bullet"] };
                } else if (section === 'leadership') {
                    newItem = { organization: "Organization", role: "Role", location: "Location", dates: "Dates", bullets: ["New bullet"] };
                }
                renderItemBlock(listDiv, newItem, section);
            };
            formContainer.appendChild(addBtn);
        } else {
            // Fallback
            const div = document.createElement('div');
            div.className = 'edit-field';
            div.innerHTML = `<label>Raw JSON</label>
                              <textarea id="edit_raw_json" style="height: 100px;">${JSON.stringify(data, null, 2)}</textarea>`;
            formContainer.appendChild(div);
        }
    }

    // Helper: Render a single item block (Experience/Project/Leadership)
    function renderItemBlock(container, item, section) {
        const div = document.createElement('div');
        div.className = 'item-block';

        let label = 'Item';
        if (section === 'experience') label = 'Job';
        if (section === 'projects') label = 'Project';
        if (section === 'leadership') label = 'Leadership';

        // Header Fields
        let headerHtml = '';
        if (section === 'experience') {
            // Fix: Check role OR title
            const roleVal = item.role || item.title || "";
            const dateVal = item.dates || item.date || "";
            const locVal = item.location || "";

            headerHtml = `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-bottom: 5px;">
                    <input type="text" class="item-company" value="${item.company || ''}" placeholder="Company">
                    <input type="text" class="item-role" value="${roleVal}" placeholder="Role">
                    <input type="text" class="item-location" value="${locVal}" placeholder="Location (e.g. New York, NY)">
                    <input type="text" class="item-dates" value="${dateVal}" placeholder="Dates" style="text-align: right;">
                </div>`;
        } else if (section === 'leadership') {
            const orgVal = item.organization || "";
            const roleVal = item.role || ""; // Resume builder uses 'role' (line 127) or 'title' (line 376)? 
            // resume_builder.py uses `lead.get('role', ...)` for BoldEntry and `lead.get('organization')` for Italic.
            // Line 376 (adapter): `create_aligned_row(lead['organization']... lead['title']...)`.
            // There seems to be a discrepancy in resume_builder.py itself between generate_resume (uses role) and create_resume_pdf (uses title in adapter?).
            // Let's use 'role' and 'organization' as primary keys.
            const dateVal = item.dates || "";
            const locVal = item.location || "";

            headerHtml = `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-bottom: 5px;">
                    <input type="text" class="item-org" value="${orgVal}" placeholder="Organization">
                    <input type="text" class="item-role" value="${roleVal}" placeholder="Role">
                    <input type="text" class="item-location" value="${locVal}" placeholder="Location">
                    <input type="text" class="item-dates" value="${dateVal}" placeholder="Dates" style="text-align: right;">
                </div>`;

        } else {
            const dateVal = item.dates || item.date || "";
            headerHtml = `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-bottom: 5px;">
                    <input type="text" class="item-name" value="${item.name || ''}" placeholder="Project Name">
                    <input type="text" class="item-tech" value="${item.tech || ''}" placeholder="Technologies">
                    <input type="text" class="item-dates" value="${dateVal}" placeholder="Dates" style="grid-column: span 2;">
                </div>`;
        }

        // Bullets
        let bulletsHtml = '';
        if (item.bullets && Array.isArray(item.bullets)) {
            item.bullets.forEach(b => {
                bulletsHtml += createBulletRow(b);
            });
        }

        div.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span style="font-weight: bold; color: #555;">${label}</span>
                <button class="remove-btn remove-item-btn">🗑️ Remove Item</button>
            </div>
            ${headerHtml}
            <div class="edit-field">
                <label>Bullets</label>
                <div class="bullet-list-container">${bulletsHtml}</div>
                <button class="add-bullet-btn" style="font-size: 10px; padding: 2px 5px; margin-top: 5px;">+ Add Bullet</button>
            </div>
        `;

        // Bind Events only for this block
        div.querySelector('.remove-item-btn').onclick = () => div.remove();

        const bulletContainer = div.querySelector('.bullet-list-container');
        div.querySelector('.add-bullet-btn').onclick = () => {
            bulletContainer.insertAdjacentHTML('beforeend', createBulletRow(""));
        };

        // Delegate bullet removal within this block
        bulletContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-bullet-btn')) {
                e.target.closest('.bullet-item').remove();
            }
        });

        container.appendChild(div);
    }

    function createBulletRow(text) {
        const safeText = text ? text.replace(/"/g, '&quot;') : '';
        // Use Grid to force width: 1fr for textarea
        return `<div class="bullet-item" style="display: grid; grid-template-columns: 1fr auto; gap: 5px; margin-bottom: 5px; width: 100%;">
                    <textarea class="bullet-input" style="width: 100%; height: 50px; resize: vertical; padding: 5px; font-family: inherit; box-sizing: border-box;">${safeText}</textarea>
                    <button class="remove-btn remove-bullet-btn" style="margin-top: 5px;">❌</button>
                </div>`;
    }

    // Helper: Extract Data from Inputs
    function parseEditor(section) {
        if (!formContainer) return null; // Safety check

        if (section === 'summary') {
            const el = document.getElementById('edit_summary_text');
            return el ? el.value : '';

        } else if (section === 'contact') {
            const inputs = formContainer.querySelectorAll('.contact-input');
            const contactData = {};
            inputs.forEach(input => {
                const key = input.dataset.key;
                if (input.value.trim()) {
                    contactData[key] = input.value.trim();
                }
            });
            return contactData;

        } else if (section === 'skills') {
            const blocks = formContainer.querySelectorAll('.item-block');
            const newSkills = {};
            blocks.forEach(block => {
                const catInput = block.querySelector('.skill-category-input');
                const valInput = block.querySelector('.skill-values-input');
                if (catInput && valInput) {
                    newSkills[catInput.value] = valInput.value;
                }
            });
            return newSkills;

        } else if (section === 'experience' || section === 'projects' || section === 'leadership') {
            const blocks = formContainer.querySelectorAll('.item-block');
            const newList = [];

            blocks.forEach(block => {
                // Get Headers
                let item = {};

                // Safely get values
                const getVal = (sel) => {
                    const el = block.querySelector(sel);
                    return el ? el.value : "";
                };

                if (section === 'experience') {
                    item.company = getVal('.item-company');
                    item.role = getVal('.item-role');
                    item.dates = getVal('.item-dates');
                    item.location = getVal('.item-location'); // Added Location
                } else if (section === 'leadership') {
                    item.organization = getVal('.item-org');
                    item.role = getVal('.item-role');
                    item.dates = getVal('.item-dates');
                    item.location = getVal('.item-location');
                } else {
                    item.name = getVal('.item-name');
                    item.tech = getVal('.item-tech');
                    item.dates = getVal('.item-dates');
                }

                // Get Bullets
                const bulletInputs = block.querySelectorAll('.bullet-input');
                item.bullets = Array.from(bulletInputs).map(b => b.value).filter(t => t.trim().length > 0);

                newList.push(item);
            });
            return newList;

        } else {
            // Fallback
            try {
                const raw = document.getElementById('edit_raw_json');
                return raw ? JSON.parse(raw.value) : currentEditingData[section];
            } catch (e) { return currentEditingData[section]; }
        }
    }

    sectionSelect.addEventListener('change', () => {
        if (!currentEditingData) return;

        // AUTO-SAVE PREVIOUS SECTION
        if (previousSection) {
            const savedData = parseEditor(previousSection);
            // Verify not-null to avoid overwriting with empty if parse failed
            if (savedData !== null) {
                currentEditingData[previousSection] = savedData;
            }
        }

        const section = sectionSelect.value;
        renderEditor(section, currentEditingData[section]);

        // Update tracker
        previousSection = section;
    });

    saveRegenBtn.addEventListener('click', async () => {
        if (!currentEditingData) return;

        // Save CURRENT section explicitly before regenerating
        const section = sectionSelect.value;
        const currentData = parseEditor(section);
        if (currentData !== null) {
            currentEditingData[section] = currentData;
        }

        try {
            // Regenerate
            saveRegenBtn.disabled = true;
            saveRegenBtn.textContent = "Regenerating...";
            statusDiv.textContent = "Regenerating PDF...";

            // Get original company name for OVERWRITE
            const result = await chrome.storage.local.get(['lastCompany']);
            const companyName = result.lastCompany || "Manual_Edit";

            const response = await fetch('http://localhost:8000/regenerate_pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    resume_data: currentEditingData,
                    company_name: companyName, // Use original company folder
                    filename: 'Pranay_Saggar_Resume.pdf' // Overwrite standard file
                })
            });

            if (!response.ok) {
                throw new Error("Regeneration failed: " + response.statusText);
            }

            const data = await response.json();

            if (data.status === 'success') {
                // Update global state
                currentViewUrl = data.view_url;

                // Save new state (REPLACE AI generated state)
                chrome.storage.local.set({
                    lastViewUrl: currentViewUrl,
                    lastResumeData: currentEditingData, // Update stored data to the edited version
                    lastStatus: "Resume updated."
                });

                statusDiv.textContent = "Resume updated successfully!";
                actionsDiv.style.display = 'block';
                editorUI.style.display = 'none';

                // Open new PDF
                chrome.tabs.create({ url: currentViewUrl });
            }

        } catch (e) {
            console.error(e);
            alert("Error: " + e.message);
        } finally {
            saveRegenBtn.disabled = false;
            saveRegenBtn.textContent = "Save & Regenerate";
        }
    });

    // --- COPY CONTENT LOGIC ---
    const copyContentBtn = document.getElementById('copyContentBtn');
    const copyUI = document.getElementById('copyUI');
    const closeCopyBtn = document.getElementById('closeCopyBtn');
    const copyList = document.getElementById('copyList');

    copyContentBtn.addEventListener('click', async () => {
        // Load data if not already loaded (similar to edit)
        let dataToCopy = null;
        const result = await chrome.storage.local.get(['lastResumeData']);
        if (result.lastResumeData) {
            dataToCopy = result.lastResumeData;
        } else {
            alert("No resume data found.");
            return;
        }

        // Show Copy UI
        copyUI.style.display = 'block';
        actionsDiv.style.display = 'none';

        renderCopyUI(dataToCopy);
    });

    closeCopyBtn.addEventListener('click', () => {
        copyUI.style.display = 'none';
        actionsDiv.style.display = 'block';
    });

    function renderCopyUI(data) {
        copyList.innerHTML = '';

        // Helper to create sections
        const createSection = (title, items, type) => {
            if (!items || items.length === 0) return;

            const header = document.createElement('h4');
            header.style.cssText = "margin: 10px 0 5px 0; color: #555; text-transform: uppercase; font-size: 11px; border-bottom: 1px solid #eee; padding-bottom: 2px;";
            header.textContent = title;
            copyList.appendChild(header);

            items.forEach((item, index) => {
                const div = document.createElement('div');
                div.style.cssText = "background: #fff; border: 1px solid #eee; border-radius: 4px; padding: 8px; margin-bottom: 8px;";

                // Title Construction
                let titleText = "";
                let subtitleText = "";

                if (type === 'experience') {
                    titleText = item.company || "Company";
                    subtitleText = item.role || item.title || "Role";
                } else if (type === 'project') {
                    titleText = item.name || "Project";
                    subtitleText = item.tech || "";
                }

                div.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 5px;">
                        <div>
                            <div style="font-weight: bold; font-size: 12px;">${titleText}</div>
                            <div style="font-size: 11px; color: #666;">${subtitleText}</div>
                        </div>
                        <button class="copy-btn" data-type="${type}" data-index="${index}" 
                            style="width: auto; padding: 4px 8px; font-size: 11px; background: #e9ecef; color: #333; border: 1px solid #ccc;">
                            📋 Copy Desc.
                        </button>
                    </div>
                    <div style="font-size: 10px; color: #888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${(item.bullets || []).join(' ')}
                    </div>
                `;
                copyList.appendChild(div);
            });
        };

        createSection('Experience', data.experience, 'experience');
        createSection('Projects', data.projects, 'project');

        // Add Event Listeners to new buttons
        const matchBtns = copyList.querySelectorAll('.copy-btn');
        matchBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const type = btn.dataset.type;
                const index = btn.dataset.index;
                let textToCopy = "";

                if (type === 'experience') {
                    const item = data.experience[index];
                    if (item.bullets) textToCopy = item.bullets.map(b => `• ${b}`).join('\n');
                } else if (type === 'project') {
                    const item = data.projects[index];
                    if (item.bullets) textToCopy = item.bullets.map(b => `• ${b}`).join('\n');
                }

                if (textToCopy) {
                    navigator.clipboard.writeText(textToCopy).then(() => {
                        const originalText = btn.textContent;
                        btn.textContent = "✅ Copied!";
                        btn.style.background = "#d4edda";
                        setTimeout(() => {
                            btn.textContent = originalText;
                            btn.style.background = "#e9ecef";
                        }, 1500);
                    });
                }
            });
        });
    }
});

