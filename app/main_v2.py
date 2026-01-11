from fastapi import FastAPI, BackgroundTasks, Request, HTTPException, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uuid
import asyncio
from typing import Optional
from app.services.beercloud import get_wordcloud_data
from app.services.image_gen import generate_image
from app.services.ocr_service import get_ocr_words
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

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

async def process_ocr_task(task_id: str, image_bytes: bytes):
    tasks[task_id] = {"status": "analyzing_image", "progress": 10}
    loop = asyncio.get_running_loop()
    
    try:
        # Step 1: OCR
        # easyocr can be slow, run in executor
        words = await loop.run_in_executor(None, get_ocr_words, image_bytes)
        
        if not words:
             tasks[task_id] = {"status": "failed", "error": "Could not extract text from image", "progress": 100}
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
async def upload_image(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "queued", "progress": 0}
    
    # Read file content
    content = await file.read()
    
    background_tasks.add_task(process_ocr_task, task_id, content)
    return {"task_id": task_id}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]
