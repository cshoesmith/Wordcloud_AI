# Lessons Learned & Technical Constraints

## Image Generation (Pollinations.ai)

### Failed Approaches
1.  **Endpoint:** `https://gen.pollinations.ai/image`
    *   **Attempt:** Using `?key=...` or `?api_key=...` query parameters.
    *   **Result:** `401 Unauthorized`.
    *   **Reason:** This endpoint requires a strict `Authorization: Bearer <key>` header or session cookie. It does not accept keys in the URL params for security.

2.  **Endpoint:** `https://image.pollinations.ai/prompt/...`
    *   **Attempt:** Requesting `model=flux`.
    *   **Result:** A generated image containing text "**WE HAVE MOVED!!** This old system is being upgraded... SIGN UP HERE -> enter.pollinations.ai".
    *   **Reason:** The public legacy endpoint has deprecated access to high-end models like Flux or is redirecting users to the new authenticated system.

### Working Solution (To Be Implemented)
*   Must use `https://gen.pollinations.ai/image` but with the API Key sent in the `Authorization` HTTP header, not the URL.
*   This means we cannot simply return a URL strings to the frontend `<img>` tag. We must create a backend proxy route that fetches the image with headers and streams it to the user.

## Text Extraction (OCR)

### Failed Approaches
1.  **Library:** `EasyOCR`
    *   **Result:** Poor accuracy on stylized fonts, crooked text, and complex beer menu layouts. Produced "garbage words".
    *   **Reason:** Lack of context and inability to handle non-standard typography common in branding.

### Working Solution
*   **Library:** `OpenAI GPT-4o (Vision)`
*   **Method:** Sending the base64 encoded image to the Chat Completion API with a prompt to "transcribe all beer names". Use `csv` or `json` formatting in the prompt for structured output.

## Server Management (Windows)

*   **Issue:** `Uvicorn` does not always release ports immediately upon shutdown or crash.
*   **Fix:** Must explicitly run `taskkill /F /IM python.exe` (or specific PIDs) before restarting the dev server to avoid `[WinError 10048] Address already in use`.
