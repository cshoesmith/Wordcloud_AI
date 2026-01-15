// Theme selector logic
document.getElementById('theme-select').addEventListener('change', (e) => {
    const customContainer = document.getElementById('custom-theme-container');
    if (e.target.value === 'Custom') {
        customContainer.classList.remove('hidden');
    } else {
        customContainer.classList.add('hidden');
    }
});

document.getElementById('generate-btn').addEventListener('click', async () => {
    const fileInput = document.getElementById('image-upload');
    const styleSelect = document.getElementById('style-select');
    const modelSelect = document.getElementById('model-select');
    const themeSelect = document.getElementById('theme-select');
    const customThemeInput = document.getElementById('custom-theme-input');

    const file = fileInput.files[0];
    const style = styleSelect.value;
    const modelProvider = modelSelect.value;
    
    let theme = themeSelect.value;
    if (theme === 'Custom') {
        theme = customThemeInput.value.trim();
        if (!theme) {
            alert("Please enter a custom theme description.");
            return;
        }
    }

    if (!file) {
        alert("Please select an image first.");
        return;
    }
    
    // Switch UI to loading state
    document.getElementById('input-section').classList.add('hidden');
    document.getElementById('progress-section').classList.remove('hidden');
    const statusText = document.getElementById('status-text');
    const progressBar = document.getElementById('progress-bar');
    
    statusText.innerText = "Uploading image...";

    try {
        // Create FormData
        const formData = new FormData();
        formData.append('file', file);
        formData.append('style', style);
        formData.append('model_provider', modelProvider);
        formData.append('theme', theme);

        // Start Upload & Generation
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errText = await response.text();
            console.error("Upload Error Response: ", response.status, response.statusText, errText); // Log to console for user
            throw new Error(`Upload Failed: ${response.status} ${response.statusText}\nServer says: ${errText}`);
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
