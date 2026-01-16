from fastapi import FastAPI, BackgroundTasks, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import uuid
import asyncio
import random
from typing import Optional
from app.services.beercloud import get_wordcloud_data
from app.services.image_gen import enrich_prompt, generate_image_dalle, generate_image_google
from app.services.ocr_service import get_ocr_words
from dotenv import load_dotenv
import time

load_dotenv()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="wardy-secret-key-12345")

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
app.mount("/images", StaticFiles(directory="images"), name="images")
templates = Jinja2Templates(directory="templates")

# Simple in-memory storage for task status
# In production, use Redis or a database
tasks = {}

class GenerateRequest(BaseModel):
    cookie: Optional[str] = None

class ResumeRequest(BaseModel):
    task_id: str
    words: str

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
             
        tasks[task_id] = {"status": "generating_art", "progress": 40, "words": words, "word_count": len(words)}
        
        # Shuffle to vary the concept if the user generates multiple times from same history
        shuffled_words = words.copy()
        random.shuffle(shuffled_words)

        # Step 2: Enrich Prompt - Increased word count for deeper context
        rich_data = await loop.run_in_executor(None, enrich_prompt, shuffled_words[:500], "dali")
        
        prompt = ""
        reasoning = ""
        
        if rich_data and isinstance(rich_data, dict):
             prompt = rich_data.get("visual_prompt", "")
             reasoning = rich_data.get("reasoning", "")
        elif rich_data and isinstance(rich_data, str):
             prompt = rich_data
        
        if not prompt:
             prompt = f"A surrealist masterpiece with {', '.join(words[:10])}"

        # Update task status with prompt info so frontend can see it immediately
        tasks[task_id] = {
            "status": "generating_art", 
            "progress": 60, 
            "words": words, 
            "word_count": len(words),
            "generated_prompt": prompt,
            "reasoning": reasoning
        }

        # Step 3: Generate Image (Defaulting to Google)
        image_url = await loop.run_in_executor(None, generate_image_google, prompt)
        
        if image_url:
            tasks[task_id] = {
                "status": "completed", 
                "progress": 100, 
                "image_url": image_url, 
                "words": words,
                "generated_prompt": prompt,
                "reasoning": reasoning
            }
        else:
            tasks[task_id] = {"status": "failed", "error": "Image generation failed", "progress": 100}
            
    except Exception as e:
        tasks[task_id] = {"status": "failed", "error": str(e), "progress": 100}

async def continue_generation_task(task_id: str, words: list[str], style: str, model_provider: str, theme: str = "Beer"):
    tasks[task_id]["status"] = "enriching_prompt"
    tasks[task_id]["progress"] = 40
    
    loop = asyncio.get_running_loop()
    try:
        # Step 2: Enrich Prompt (GPT-4o)
        
        # Shuffle words to ensure variety if the list is long, avoiding "header bias"
        shuffled_words = words.copy()
        random.shuffle(shuffled_words)
        
        # Pass a larger chunk of words (500) to allow for the new multi-stage "all words" reasoning
        rich_data = await loop.run_in_executor(None, enrich_prompt, shuffled_words[:500], style, theme)
        
        prompt = ""
        reasoning = ""
        
        if rich_data and isinstance(rich_data, dict):
             prompt = rich_data.get("visual_prompt", "")
             reasoning = rich_data.get("reasoning", "")
        elif rich_data and isinstance(rich_data, str):
             prompt = rich_data

        if not prompt:
             # Fallback
             prompt = f"A list of items: {', '.join(words[:20])}"

        # Update task with prompt info
        tasks[task_id] = {
            "status": "generating_art", 
            "progress": 70, 
            "words": words, 
            "word_count": len(words),
            "generated_prompt": prompt, 
            "reasoning": reasoning
        }
        
        # Step 3: Generate Image based on Provider
        image_url = None
        if model_provider == "dalle":
             image_url = await loop.run_in_executor(None, generate_image_dalle, prompt)
        elif model_provider == "google":
             from app.services.image_gen import generate_image_google
             image_url = await loop.run_in_executor(None, generate_image_google, prompt)
        else:
             # Default to Google if unknown
             from app.services.image_gen import generate_image_google
             image_url = await loop.run_in_executor(None, generate_image_google, prompt)
        
        if image_url:
            tasks[task_id] = {
                "status": "completed", 
                "progress": 100, 
                "image_url": image_url, 
                "words": words, 
                "generated_prompt": prompt, 
                "reasoning": reasoning
            }
        else:
            tasks[task_id] = {"status": "failed", "error": "Image generation failed", "progress": 100}

    except Exception as e:
        tasks[task_id] = {"status": "failed", "error": str(e), "progress": 100}

async def process_ocr_task(task_id: str, image_bytes: bytes, style: str, model_provider: str, theme: str = "Beer"):
    tasks[task_id] = {"status": "analyzing_image", "progress": 10}
    loop = asyncio.get_running_loop()
    
    try:
        # Step 1: OCR (GPT-4o Vision)
        words = await loop.run_in_executor(None, get_ocr_words, image_bytes)
        
        if not words:
             # If no words found, wait for manual input
             tasks[task_id] = {
                 "status": "waiting_for_input", 
                 "progress": 20, 
                 "style": style, 
                 "model_provider": model_provider,
                 "theme": theme,
                 "error": "No text detected. Please enter words manually."
             }
             return

        # Proceed to generation if words found
        await continue_generation_task(task_id, words, style, model_provider, theme)

    except Exception as e:
        tasks[task_id] = {"status": "failed", "error": str(e), "progress": 100}


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if password == "Wardy123":
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid Password"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate")
async def generate(request: Request, request_body: GenerateRequest, background_tasks: BackgroundTasks):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "queued", "progress": 0}
    background_tasks.add_task(process_wordcloud, task_id, request_body.cookie)
    return {"task_id": task_id}

@app.post("/upload")
async def upload_image(request: Request, background_tasks: BackgroundTasks, file: UploadFile = File(...), style: str = Form("dali"), model_provider: str = Form("google"), theme: str = Form("Beer")):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    print(f"Received upload: {file.filename}, content_type={file.content_type}, style={style}, model_provider={model_provider}, theme={theme}")
    try:
        task_id = str(uuid.uuid4())
        tasks[task_id] = {"status": "queued", "progress": 0}
        
        # Read file content
        content = await file.read()
        print(f"Read {len(content)} bytes")
        
        background_tasks.add_task(process_ocr_task, task_id, content, style, model_provider, theme)
        return {"task_id": task_id}
    except Exception as e:
        print(f"UPLOAD ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_manual")
async def generate_manual(request: Request, background_tasks: BackgroundTasks, 
                          words: str = Form(...), 
                          style: str = Form("dali"), 
                          model_provider: str = Form("google"), 
                          theme: str = Form("Beer")):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    print(f"Received manual generation request: {len(words)} chars, style={style}, theme={theme}")
    
    # Process words
    words_list = [w.strip() for w in words.split(",")]
    # Remove empty
    words_list = [w for w in words_list if w]

    if not words_list or len(words_list) < 1:
        raise HTTPException(status_code=400, detail="Please provide at least one word.")

    try:
        task_id = str(uuid.uuid4())
        tasks[task_id] = {"status": "queued", "progress": 0}
        
        # Start generation directly, skipping OCR
        background_tasks.add_task(continue_generation_task, task_id, words_list, style, model_provider, theme)
        
        return {"task_id": task_id}
    except Exception as e:
        print(f"MANUAL GEN ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/resume_task")
async def resume_task(request: Request, body: ResumeRequest, background_tasks: BackgroundTasks):
    if not request.session.get("authenticated"):
         raise HTTPException(status_code=401, detail="Unauthorized")
    
    task_id = body.task_id
    if task_id not in tasks:
         raise HTTPException(status_code=404, detail="Task not found")
    
    task_state = tasks[task_id]
    if task_state.get("status") != "waiting_for_input":
         return {"message": "Task is not waiting for input", "status": task_state.get("status")}
    
    # Process words
    words_list = [w.strip() for w in body.words.split(",")]
    # Remove empty
    words_list = [w for w in words_list if w]
    
    if not words_list:
        raise HTTPException(status_code=400, detail="No valid words provided")
        
    # Get previous context
    style = task_state.get("style", "dali")
    model_provider = task_state.get("model_provider", "google")
    theme = task_state.get("theme", "Beer")
    
    # Update status immediately
    tasks[task_id]["status"] = "resuming"
    tasks[task_id]["progress"] = 30
    
    # Launch background task
    background_tasks.add_task(continue_generation_task, task_id, words_list, style, model_provider, theme)
    
    return {"status": "ok", "message": "Resuming generation"}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]
