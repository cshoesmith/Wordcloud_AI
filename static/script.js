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

// 1. Setup Input Mode Switcher
setupXorGroup('input-mode-group', 'input-mode-value', (mode) => {
    const uploadContainer = document.getElementById('upload-container');
    const manualTextContainer = document.getElementById('manual-text-container');
    
    if (mode === 'upload') {
        uploadContainer.classList.remove('hidden');
        manualTextContainer.classList.add('hidden');
    } else {
        uploadContainer.classList.add('hidden');
        manualTextContainer.classList.remove('hidden');
    }
});

// 2. Setup Theme Switcher
setupXorGroup('theme-group', 'theme-value', (theme) => {
    const customContainer = document.getElementById('custom-theme-container');
    if (theme === 'Custom') {
        customContainer.classList.remove('hidden');
    } else {
        customContainer.classList.add('hidden');
    }
});

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

// 3. Setup Style Switcher with Preview Update
setupXorGroup('style-group', 'style-value', (styleKey) => {
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
});

// 4. Setup Model Switcher
setupXorGroup('model-group', 'model-value', null);


document.getElementById('generate-btn').addEventListener('click', async () => {
    // Determine Input Mode from hidden input
    const inputMode = document.getElementById('input-mode-value').value;

    // Get values from hidden inputs
    const style = document.getElementById('style-value').value;
    const modelProvider = document.getElementById('model-value').value;
    
    let theme = document.getElementById('theme-value').value;
    const customThemeInput = document.getElementById('custom-theme-input');

    if (theme === 'Custom') {
        theme = customThemeInput.value.trim();
        if (!theme) {
            alert("Please enter a custom theme description.");
            return;
        }
    }

    let endpoint = '/upload';
    const formData = new FormData();
    formData.append('style', style);
    formData.append('model_provider', modelProvider);
    formData.append('theme', theme);

    if (inputMode === 'upload') {
        const fileInput = document.getElementById('image-upload');
        const file = fileInput.files[0];
        if (!file) {
            alert("Please select an image to upload.");
            return;
        }
        formData.append('file', file);
    } else {
        // Manual Input Mode
        endpoint = '/generate_manual';
        const manualText = document.getElementById('manual-text-input').value.trim();
        if (!manualText) {
            alert("Please enter some words to generate your masterpiece.");
            return;
        }
        formData.append('words', manualText);
    }
    
    // Switch UI to loading state
    document.getElementById('input-section').classList.add('hidden');
    document.getElementById('progress-section').classList.remove('hidden');
    const statusText = document.getElementById('status-text');
    const progressBar = document.getElementById('progress-bar');
    
    if (inputMode === 'upload') {
        statusText.innerText = "Uploading image...";
    } else {
        statusText.innerText = "Processing words...";
        progressBar.style.width = "30%";
    }

    try {
        // Start Request
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errText = await response.text();
            console.error("Error Response: ", response.status, response.statusText, errText); 
            // Reset UI on error (simple)
            document.getElementById('input-section').classList.remove('hidden');
            document.getElementById('progress-section').classList.add('hidden');
            throw new Error(`Request Failed: ${response.statusText} \n ${errText}`);
        }

        const data = await response.json();
        const taskId = data.task_id;

        // Poll for status
        const pollInterval = setInterval(async () => {
            try {
                const statusRes = await fetch(`/status/${taskId}`);
                if (!statusRes.ok) return;

                const statusData = await statusRes.json();
                
                progressBar.style.width = statusData.progress + "%";
                
                
                if (statusData.status === 'analyzing_image') {
                    statusText.innerText = "Reading text from image (this may take a moment)...";
                } else if (statusData.status === 'waiting_for_input') {
                    // Start Waiting for Manual Input
                    document.getElementById('progress-section').classList.add('hidden');
                    document.getElementById('manual-input-section').classList.remove('hidden');
                    
                    // One-time listener for the resume button
                    const resumeBtn = document.getElementById('resume-btn');
                    // Avoid stacking listeners by cloning/replacing
                    const newBtn = resumeBtn.cloneNode(true);
                    resumeBtn.parentNode.replaceChild(newBtn, resumeBtn);
                    
                    newBtn.addEventListener('click', async () => {
                        const words = document.getElementById('manual-words-input').value;
                        if (!words || words.length < 3) {
                            alert("Please enter at least 3 descriptive words.");
                            return;
                        }
                        
                        // Switch back to loading
                        document.getElementById('manual-input-section').classList.add('hidden');
                        document.getElementById('progress-section').classList.remove('hidden');
                        statusText.innerText = "Resuming creation...";
                        
                        try {
                            const resRes = await fetch('/resume_task', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({ task_id: taskId, words: words })
                            });
                            if(!resRes.ok) throw new Error("Failed to resume");
                            
                            // Polling continues automatically since we didn't clear interval
                        } catch (e) {
                             statusText.innerText = "Error Resuming: " + e.message;
                             clearInterval(pollInterval);
                        }
                    });
                    
                } else if (statusData.status === 'generating_art') {
                    const wordExample = statusData.words ? statusData.words.slice(0, 5).join(", ") : "beers";
                    statusText.innerText = `Found: ${wordExample}...\nDreaming up a masterpiece...`;
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

    } catch (e) {
        statusText.innerText = "Error: " + e.message;
        // Don't hide progress immediately so user sees error
    }
});

function showResult(data) {
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('result-section').classList.remove('hidden');
    
    const img = document.getElementById('generated-image');
    img.src = data.image_url;
    
    const downloadBtn = document.getElementById('download-btn');
    downloadBtn.href = data.image_url;

    // Populate details
    document.getElementById('art-reasoning').innerText = data.reasoning || "The AI meditated on your request but remained silent on its methods.";
    document.getElementById('art-prompt').innerText = data.generated_prompt || "Prompt data unavailable.";
    document.getElementById('extracted-words').innerText = (data.words && data.words.length > 0) ? data.words.join(" • ") : "No specific words identified.";
}
