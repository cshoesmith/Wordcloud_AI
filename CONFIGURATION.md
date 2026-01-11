# Wordcloud AI Configuration

## Prerequisites

- **Python 3.10+**
- **Git**

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/cshoesmith/Wordcloud_AI.git
    cd Wordcloud_AI
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # Windows
    python -m venv .venv
    .venv\Scripts\activate

    # Linux/Mac
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    python -m playwright install
    ```

## Environment Variables

Create a `.env` file in the root directory of the project. This file is ignored by Git to protect your secrets.

Add the following keys to your `.env` file:

```ini
# OpenAI API Key (Required for Text Extraction and Prompt Enrichment)
# Must have access to GPT-4o (Vision and Chat)
OPENAI_API_KEY=sk-proj-...

# Pollinations.ai API Key (Optional/Required for specific models)
# Used for image generation if private/paid tier is needed.
# If not provided, the public endpoint might be used or functionality limited.
POLLINATIONS_API_KEY=pk_...
```

## Running the Application

1.  **Start the FastAPI server:**
    ```bash
    python -m uvicorn app.main:app --reload
    ```
    The server will start at `http://127.0.0.1:8000`.

2.  **Access the Interface:**
    Open your web browser and navigate to `http://127.0.0.1:8000`.

## Architecture

-   **Frontend:** HTML/JS serving a simple upload interface.
-   **Backend:** FastAPI (Python).
-   **Services:**
    -   `ocr_service.py`: Uses GPT-4o Vision to extract text from beer menu images.
    -   `image_gen.py`: Generates images using Pollinations.ai (Flux model), enriched by GPT-4o prompts.
