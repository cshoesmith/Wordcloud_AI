document.getElementById('generate-btn').addEventListener('click', async () => {
    const fileInput = document.getElementById('image-upload');
    const styleSelect = document.getElementById('style-select');
    const file = fileInput.files[0];
    const style = styleSelect.value;

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
                } else if (statusData.status === 'generating_art') {
                    const wordExample = statusData.words ? statusData.words.slice(0, 5).join(", ") : "beers";
                    statusText.innerText = `Found: ${wordExample}...\nDreaming up a masterpiece...`;
                } else if (statusData.status === 'completed') {
                    clearInterval(pollInterval);
                    showResult(statusData.image_url);
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

function showResult(imageUrl) {
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('result-section').classList.remove('hidden');
    
    const img = document.getElementById('generated-image');
    img.src = imageUrl;
    
    const downloadBtn = document.getElementById('download-btn');
    downloadBtn.href = imageUrl;
}
