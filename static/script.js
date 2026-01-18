/* --- Global State --- */
let currentStep = 1;

/* --- Initialization --- */
document.addEventListener('DOMContentLoaded', () => {
    // 1. Setup Input Mode Switcher (Step 1)
    setupXorGroup('input-mode-group', 'input-mode-value', (mode) => {
        const uploadContainer = document.getElementById('upload-container');
        const manualTextContainer = document.getElementById('manual-text-container');
        const untappdContainer = document.getElementById('untappd-container');
        
        uploadContainer.classList.add('hidden');
        manualTextContainer.classList.add('hidden');
        untappdContainer.classList.add('hidden');

        if (mode === 'upload') {
            uploadContainer.classList.remove('hidden');
        } else if (mode === 'manual') {
            manualTextContainer.classList.remove('hidden');
        } else if (mode === 'untappd') {
            untappdContainer.classList.remove('hidden');
        }
    });

    // Check URL params for Untappd connection
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('untappd_connected')) {
        const untappdBtn = document.querySelector('button[data-value="untappd"]');
        if (untappdBtn) {
            untappdBtn.click();
            // Optional: Auto-advance if we know it worked? 
            // Better to let user see "Connected" and click Next.
        }
    }

    // 2. Setup Theme Switcher (Modal)
    setupXorGroup('theme-group', 'theme-value', (theme) => {
        const customContainer = document.getElementById('custom-theme-container');
        if (theme === 'Custom') {
            customContainer.classList.remove('hidden');
        } else {
            customContainer.classList.add('hidden');
        }
    });

    // 3. Setup Style Switcher (Step 2)
    setupXorGroup('style-group', 'style-value', (styleKey) => {
        updateStylePreview(styleKey);
    });

    // 4. Setup Model Switcher (Modal)
    setupXorGroup('model-group', 'model-value', null);

    // 5. Modal Logic
    setupModal();
});


/* --- Helper Functions --- */

// General logic to handle any XOR button group
function setupXorGroup(groupId, hiddenInputId, callback) {
    const group = document.getElementById(groupId);
    const input = document.getElementById(hiddenInputId);
    
    if (!group || !input) return;

    const buttons = group.querySelectorAll('.xor-btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove selected from all in this group
            buttons.forEach(b => b.classList.remove('selected'));
            // Add to clicked
            btn.classList.add('selected');
            // Update value
            const newVal = btn.getAttribute('data-value');
            input.value = newVal;

            // Optional callback for logic updates
            if (callback) callback(newVal);
        });
    });
}

function setupModal() {
    const modal = document.getElementById('settings-modal');
    const btn = document.getElementById('settings-btn');
    const span = document.getElementsByClassName("close-modal")[0];
    const saveBtn = document.getElementById('save-settings-btn');

    if (!modal) return;

    btn.onclick = function() {
        modal.style.display = "block";
    }

    // Both X and Save button close the modal
    const closeModal = function() {
        modal.style.display = "none";
    }

    if (span) span.onclick = closeModal;
    if (saveBtn) saveBtn.onclick = closeModal;

    window.onclick = function(event) {
        if (event.target == modal) {
            closeModal();
        }
    }
}

// Style Preview Data
const styleDetails = {
    'dali': {
        img: '/images/dali.png',
        desc: '"Dreamlike visuals with melting forms and bizarre landscapes."'
    },
    'scarry': {
        img: '/images/richard_scarry.png',
        desc: '"Busy, colorful, detailed 1970s illustration style."'
    },
    'picasso': {
        img: '/images/picasso.png',
        desc: '"Geometric shapes, fragmented perspectives, and abstract forms."'
    },
    'cyberpunk': {
        img: '/images/steampunk.png',
        desc: '"Neon lights, high-tech low-life, futuristic cityscapes."'
    },
    'technology': {
        img: '/images/abstracttech.png',
        desc: '"Clean lines, circuit board patterns, and modern digital aesthetics."'
    }
};

function updateStylePreview(styleKey) {
    const info = styleDetails[styleKey];
    if (info) {
        const img = document.getElementById('style-preview-img');
        const desc = document.getElementById('style-description');
        
        // Simple fade effect
        img.style.opacity = '0.5';
        setTimeout(() => {
            img.src = info.img;
            desc.textContent = info.desc;
            img.onload = () => { img.style.opacity = '1'; };
        }, 150);
    }
}


/* --- Wizard Navigation --- */

window.goToStep = function(step) {
    // Validation before moving forward
    if (step > currentStep) {
        if (!validateStep(currentStep)) return;
    }

    // Hide all steps
    document.querySelectorAll('.wizard-step').forEach(el => el.classList.remove('active'));
    
    // Show target step
    document.getElementById(`step-${step}`).classList.add('active');
    currentStep = step;
    
    // Scroll to top
    window.scrollTo(0,0);
}

function validateStep(step) {
    if (step === 1) {
        const mode = document.getElementById('input-mode-value').value;
        if (mode === 'upload') {
            const fileInput = document.getElementById('image-upload');
            if (fileInput.files.length === 0) {
                alert("Please select an image first.");
                return false;
            }
        } else if (mode === 'manual') {
            const text = document.getElementById('manual-text-input').value.trim();
            if (text.length < 3) {
                alert("Please enter at least 3 descriptive words.");
                return false;
            }
        }
        // Untappd needs check? Maybe connected state check?
    }
    return true;
}


/* --- Generation Logic --- */

document.getElementById('generate-btn').addEventListener('click', async () => {
    // Determine Input Mode from hidden input
    const inputMode = document.getElementById('input-mode-value').value;

    // Get values from hidden settings
    const style = document.getElementById('style-value').value;
    const modelProvider = document.getElementById('model-value').value;
    
    let theme = document.getElementById('theme-value').value;
    const customThemeInput = document.getElementById('custom-theme-input');

    if (theme === 'Custom') {
        theme = customThemeInput.value.trim();
        if (!theme) {
            // Open modal to prompt logic? Or just alert.
            alert("Please enter a custom theme description in Settings (Top Left).");
            return;
        }
    }

    let endpoint = '';
    const formData = new FormData();
    formData.append('style', style);
    formData.append('model_provider', modelProvider);
    formData.append('theme', theme);

    if (inputMode === 'upload') {
        endpoint = '/upload';
        const fileInput = document.getElementById('image-upload');
        const file = fileInput.files[0];
        if (!file) {
            alert("No file found. Please go back to Step 1.");
            goToStep(1);
            return;
        }
        formData.append('file', file);
    } else if (inputMode === 'manual') {
        endpoint = '/generate_manual';
        const manualText = document.getElementById('manual-text-input').value.trim();
        formData.append('words', manualText);
    } else if (inputMode === 'untappd') {
        endpoint = '/generate_untappd';
    }
    
    // Hide Wizard, Show Progress
    document.querySelectorAll('.wizard-step').forEach(el => el.classList.remove('active'));
    document.getElementById('progress-section').classList.remove('hidden');
    
    const statusText = document.getElementById('status-text');
    const progressBar = document.getElementById('progress-bar');
    
    // Reset defaults
    statusText.style.color = "var(--gold)";
    progressBar.style.backgroundColor = "var(--gold)"; 

    if (inputMode === 'upload') {
        statusText.innerText = "Uploading & Analyzing...";
    } else if (inputMode === 'untappd') {
        statusText.innerText = "Fetching Untappd history...";
        progressBar.style.width = "20%";
    } else {
        statusText.innerText = "Processing words...";
        progressBar.style.width = "30%";
    }

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`Request Failed: ${response.statusText} \n ${errText}`);
        }

        const data = await response.json();
        const taskId = data.task_id;

        pollTask(taskId);

    } catch (e) {
        statusText.innerText = "Error: " + e.message;
        statusText.style.color = "red";
    }
});

function pollTask(taskId) {
    const statusText = document.getElementById('status-text');
    const progressBar = document.getElementById('progress-bar');

    const pollInterval = setInterval(async () => {
        try {
            const statusRes = await fetch(`/status/${taskId}`);
            if (!statusRes.ok) return;

            const statusData = await statusRes.json();
            progressBar.style.width = statusData.progress + "%";
            
            if (statusData.status === 'analyzing_image') {
                statusText.innerText = "Reading text from image...";
            } else if (statusData.status === 'waiting_for_input') {
                // Manual Disambiguation Needed
                document.getElementById('progress-section').classList.add('hidden');
                document.getElementById('manual-input-section').classList.remove('hidden');
                
                // One-time listener for the resume button
                const resumeBtn = document.getElementById('resume-btn');
                const newBtn = resumeBtn.cloneNode(true);
                resumeBtn.parentNode.replaceChild(newBtn, resumeBtn);
                
                newBtn.addEventListener('click', async () => {
                    const words = document.getElementById('manual-words-input').value;
                    if (!words || words.length < 3) {
                        alert("Please enter at least 3 descriptive words.");
                        return;
                    }
                    
                    document.getElementById('manual-input-section').classList.add('hidden');
                    document.getElementById('progress-section').classList.remove('hidden');
                    statusText.innerText = "Resuming creation...";
                    
                    try {
                        await fetch('/resume_task', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ task_id: taskId, words: words })
                        });
                    } catch (e) {
                         statusText.innerText = "Error Resuming: " + e.message;
                         clearInterval(pollInterval);
                    }
                });
                
            } else if (statusData.status === 'generating_art') {
                let wordExample = "beers";
                try {
                    if (statusData.words) {
                        if (Array.isArray(statusData.words)) {
                            wordExample = statusData.words.slice(0, 3).join(", ");
                        } else if (typeof statusData.words === 'object') {
                            const flat = Object.values(statusData.words).flat();
                            wordExample = flat.slice(0, 3).join(", ");
                        }
                    }
                } catch(e) { console.log(e); }
                statusText.innerText = `Dreaming of ${wordExample}...`;
            } else if (statusData.status === 'completed') {
                clearInterval(pollInterval);
                showResult(statusData);
            } else if (statusData.status === 'failed') {
                clearInterval(pollInterval);
                statusText.innerText = "Error: " + statusData.error;
                statusText.style.color = "red";
                progressBar.style.backgroundColor = "red";
            }
        } catch (err) {
            console.error(err);
        }
    }, 1000);
}

function showResult(data) {
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('result-section').classList.remove('hidden');
    
    const img = document.getElementById('generated-image');
    img.src = data.image_url;
    
    const downloadBtn = document.getElementById('download-btn');
    downloadBtn.href = data.image_url;

    // Populate details
    document.getElementById('art-reasoning').innerText = data.reasoning || "Reasoning unavailable.";
    document.getElementById('art-prompt').innerText = data.generated_prompt || "...";
    
    let displayWords = "";
    try {
        if (data.words) {
            if (Array.isArray(data.words)) {
                 displayWords = data.words.join(" • ");
            } else if (typeof data.words === 'object') {
                 // Group by category for nicer display? Or just flatten.
                 // Flatten for now to match original UI
                 displayWords = Object.values(data.words).flat().join(" • ");
            }
        }
    } catch(e) {}
    document.getElementById('extracted-words').innerText = displayWords;
}
