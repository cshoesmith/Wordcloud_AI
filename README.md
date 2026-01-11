# Wordcloud AI Art

A web application that takes your beer history (via Untappd/BeerCloud) and transforms extracted keywords into a surrealist, Dali-style masterpiece using AI.

## Features
- **Data Extraction**: Connects to `beercloud.wardy.au` (simulated via cookie) to find your top beer descriptors.
- **AI Art Generation**: Uses OpenAI's DALL-E 3 to dream up a unique scene based on those words.
- **Gallery UI**: Presents the result in an elegant, digital picture frame.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Variables**:
    Create a `.env` file in the root directory:
    ```
    OPENAI_API_KEY=your_openai_api_key_here
    ```

3.  **Run the App**:
    ```bash
    uvicorn app.main:app --reload
    ```

4.  **Open in Browser**:
    Go to `http://127.0.0.1:8000`.

## Usage
1.  Paste your session cookie string (or use the test value `simulated_success` to bypass extraction and see the art generation with test words).
2.  Click "Generate Masterpiece".
3.  Wait for the AI to dream.
4.  Download your framed art.
