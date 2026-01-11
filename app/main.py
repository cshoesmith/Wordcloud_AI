from fastapi import FastAPI, BackgroundTasks, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uuid
import asyncio
from typing import Optional
from app.services.beercloud import get_wordcloud_data
from app.services.image_gen import generate_image, generate_image_from_prompt, enrich_prompt, generate_image_dalle
from app.services.ocr_service import get_ocr_words
from dotenv import load_dotenv
import time

load_dotenv()

app = FastAPI()

# Middleware for logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    print(f"REQUEST START: {request.method} {request.url}")
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        print(f"REQUEST END: {request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.4f}s")
        return response
    except Exception as e:
        print(f"REQUEST ERROR: {request.method} {request.url} - Exception: {e}")
        raise e

@app.on_event("startup")
async def startup_event():
    print("Startup: Registered routes:")
    for route in app.routes:
        if hasattr(route, "methods"):
             print(f" - {route.path} {route.methods}")
        else:
             print(f" - {route.path} [Mount]")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Simple in-memory storage for task status
# In production, use Redis or a database
tasks = {}

class GenerateRequest(BaseModel):
    cookie: Optional[str] = None

# Kept for backward compatibility if needed
async def process_wordcloud(task_id: str, cookie: str):
    tasks[task_id] = {"status": "extracting_words", "progress": 10}
    loop = asyncio.get_running_loop()

    # Step 1: Extract words
    try:
        words = await loop.run_in_executor(None, get_wordcloud_data, cookie)
        if not words:
             tasks[task_id] = {"status": "failed", "error": "Could not extract words", "progress": 100}
             return
             
        tasks[task_id] = {"status": "generating_art", "progress": 50, "words": words, "word_count": len(words)}
        
        # Step 2: Generate Image
        image_url = await loop.run_in_executor(None, generate_image, words)
        
        if image_url:
            tasks[task_id] = {"status": "completed", "progress": 100, "image_url": image_url, "words": words}
        else:
            tasks[task_id] = {"status": "failed", "error": "Image generation failed", "progress": 100}
            
    except Exception as e:
        tasks[task_id] = {"status": "failed", "error": str(e), "progress": 100}

async def process_ocr_task(task_id: str, image_bytes: bytes, style: str, use_dalle: bool):
    tasks[task_id] = {"status": "analyzing_image", "progress": 10}
    loop = asyncio.get_running_loop()
    
    try:
        # Step 1: OCR (GPT-4o Vision)
        words = await loop.run_in_executor(None, get_ocr_words, image_bytes)
        
        if not words:
             tasks[task_id] = {"status": "failed", "error": "Could not extract text from image", "progress": 100}
             return

        # Step 2: Enrich Prompt (GPT-4o)
        tasks[task_id] = {"status": "enriching_prompt", "progress": 40, "words": words, "word_count": len(words)}
        
        rich_prompt = await loop.run_in_executor(None, enrich_prompt, words[:30], style)
        if not rich_prompt:
             # Fallback
             rich_prompt = f"A list of items: {', '.join(words[:20])}"

        # Step 3: Generate Image (Pollinations Flux OR DALL-E)
        tasks[task_id] = {"status": "generating_art", "progress": 70, "words": words, "word_count": len(words)}
        
        if use_dalle:
             image_url = await loop.run_in_executor(None, generate_image_dalle, rich_prompt)
        else:
             image_url = await loop.run_in_executor(None, generate_image_from_prompt, rich_prompt)
        
        if image_url:
            tasks[task_id] = {"status": "completed", "progress": 100, "image_url": image_url, "words": words}
        else:
            tasks[task_id] = {"status": "failed", "error": "Image generation failed", "progress": 100}

    except Exception as e:
        tasks[task_id] = {"status": "failed", "error": str(e), "progress": 100}


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
async def generate(request: GenerateRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "queued", "progress": 0}
    background_tasks.add_task(process_wordcloud, task_id, request.cookie)
    return {"task_id": task_id}

@app.post("/upload")
async def upload_image(background_tasks: BackgroundTasks, file: UploadFile = File(...), style: str = Form("dali"), use_dalle: bool = Form(False)):
    print(f"Received upload: {file.filename}, content_type={file.content_type}, style={style}, use_dalle={use_dalle}")
    try:
        task_id = str(uuid.uuid4())
        tasks[task_id] = {"status": "queued", "progress": 0}
        
        # Read file content
        content = await file.read()
        print(f"Read {len(content)} bytes")
        
        background_tasks.add_task(process_ocr_task, task_id, content, style, use_dalle)
        return {"task_id": task_id}
    except Exception as e:
        print(f"UPLOAD ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]
