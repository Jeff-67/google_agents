from pathlib import Path
from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging
import asyncio
import json
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Store messages temporarily to connect POST and GET
SSE_MESSAGES = {}

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def root():
    """Serves the index.html"""
    return FileResponse(STATIC_DIR / "index.html")

# Proxy endpoints
@app.post("/proxy/session/{app_name}/{user_id}/{session_id}")
async def create_session_proxy(app_name: str, user_id: str, session_id: str, request: Request):
    """Proxy for session creation"""
    try:
        json_data = await request.json()
        logger.info(f"Creating session for {app_name}/{user_id}/{session_id}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"http://0.0.0.0:8000/apps/{app_name}/users/{user_id}/sessions/{session_id}",
                json=json_data
            )
            return JSONResponse(
                content=response.json(),
                status_code=response.status_code
            )
    except httpx.TimeoutException:
        logger.error("Timeout connecting to ADK server")
        return JSONResponse(
            content={"detail": "Connection to ADK server timed out"},
            status_code=504
        )
    except Exception as e:
        logger.error(f"Error in create_session_proxy: {str(e)}")
        return JSONResponse(
            content={"detail": str(e)},
            status_code=500
        )

@app.post("/proxy/run")
async def run_proxy(request: Request):
    """Proxy for run endpoint (non-streaming)"""
    try:
        json_data = await request.json()
        logger.info(f"Proxying run request for {json_data.get('app_name')}/{json_data.get('session_id')}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "http://0.0.0.0:8000/run",
                json=json_data
            )
            return JSONResponse(
                content=response.json(),
                status_code=response.status_code
            )
    except httpx.TimeoutException:
        logger.error("Timeout connecting to ADK server")
        return JSONResponse(
            content={"detail": "Connection to ADK server timed out - the AI may need more time to process your request"},
            status_code=504
        )
    except Exception as e:
        logger.error(f"Error in run_proxy: {str(e)}")
        return JSONResponse(
            content={"detail": str(e)},
            status_code=500
        )

@app.post("/proxy/prepare_sse")
async def prepare_sse_proxy(request: Request):
    """Prepare data for SSE streaming"""
    try:
        json_data = await request.json()
        
        # Set streaming to true
        json_data["streaming"] = True
            
        # Generate a unique ID for this request
        request_id = str(uuid.uuid4())
        
        # Store the request data
        SSE_MESSAGES[request_id] = {
            "data": json_data,
            "status": "pending"
        }
        
        logger.info(f"Prepared SSE request {request_id} for {json_data.get('app_name')}/{json_data.get('session_id')}")
        
        # Return the ID to be used for the SSE connection
        return JSONResponse({
            "request_id": request_id
        })
    except Exception as e:
        logger.error(f"Error in prepare_sse_proxy: {str(e)}")
        return JSONResponse(
            content={"detail": str(e)},
            status_code=500
        )

@app.get("/proxy/sse_connect/{request_id}")
async def sse_connect(request_id: str):
    """SSE endpoint that connects to a prepared request"""
    try:
        # Check if the request exists
        if request_id not in SSE_MESSAGES:
            return JSONResponse(
                content={"detail": "Request not found"},
                status_code=404
            )
            
        # Get the request data
        request_data = SSE_MESSAGES[request_id]["data"]
        logger.info(f"SSE connect for request {request_id}")
        
        # Mark as in-progress
        SSE_MESSAGES[request_id]["status"] = "in-progress"
        
        async def event_generator():
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("POST", "http://0.0.0.0:8000/run_sse", json=request_data) as response:
                        if response.status_code != 200:
                            error_content = await response.read()
                            yield f"data: {error_content.decode('utf-8')}\n\n"
                            return
                            
                        async for chunk in response.aiter_text():
                            # Forward each chunk directly
                            if chunk.strip():
                                yield chunk
                
                # Clean up the request data after completion
                if request_id in SSE_MESSAGES:
                    SSE_MESSAGES[request_id]["status"] = "completed"
                    # Keep for a bit but eventually clean up
                    asyncio.create_task(cleanup_request(request_id, delay=60))
            except Exception as e:
                logger.error(f"Error in SSE streaming for {request_id}: {str(e)}")
                yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
                if request_id in SSE_MESSAGES:
                    SSE_MESSAGES[request_id]["status"] = "error"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Error in sse_connect: {str(e)}")
        return JSONResponse(
            content={"detail": str(e)},
            status_code=500
        )

async def cleanup_request(request_id, delay=60):
    """Clean up request data after a delay"""
    await asyncio.sleep(delay)
    if request_id in SSE_MESSAGES:
        del SSE_MESSAGES[request_id]
        logger.info(f"Cleaned up request {request_id}")