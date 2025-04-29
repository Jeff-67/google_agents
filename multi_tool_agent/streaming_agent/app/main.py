from pathlib import Path
from fastapi import FastAPI, Request, Body
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

# Store user location information
USER_LOCATIONS = {}

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

# Location endpoints
@app.post("/proxy/store_location")
async def store_location(location: dict = Body(...)):
    """Store browser location data"""
    try:
        # We could use a more complex storage system with user IDs in the future
        global USER_LOCATIONS
        USER_LOCATIONS["browser"] = location
        logger.info(f"Stored browser location: {location['lat']:.4f}, {location['lng']:.4f}")
        return JSONResponse({"status": "success"})
    except Exception as e:
        logger.error(f"Error storing location: {str(e)}")
        return JSONResponse(
            content={"detail": str(e)},
            status_code=500
        )

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
            response_data = response.json()
            
            # Check for get_current_place function calls and intercept responses
            processed_data = intercept_function_calls(response_data)
            
            return JSONResponse(
                content=processed_data,
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
                function_call_detected = False
                current_function_id = None
                
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("POST", "http://0.0.0.0:8000/run_sse", json=request_data) as response:
                        if response.status_code != 200:
                            error_content = await response.read()
                            yield f"data: {error_content.decode('utf-8')}\n\n"
                            return
                            
                        async for chunk in response.aiter_text():
                            # Skip empty chunks
                            if not chunk.strip():
                                continue
                                
                            # Process each chunk to intercept function calls
                            if chunk.startswith("data: "):
                                chunk_data = chunk[6:]  # Remove "data: " prefix
                                try:
                                    data = json.loads(chunk_data)
                                    
                                    # Process function calls and modify responses if needed
                                    if data.get("content") and data["content"].get("parts"):
                                        for part_index, part in enumerate(data["content"]["parts"]):
                                            # Check for functionCall to get_current_place
                                            if part.get("functionCall") and part["functionCall"].get("name") == "get_current_place":
                                                function_call_detected = True
                                                current_function_id = part["functionCall"].get("id")
                                                logger.info(f"Detected get_current_place call with ID: {current_function_id}")
                                            
                                            # Check for functionResponse to get_current_place
                                            if (function_call_detected and 
                                                part.get("functionResponse") and 
                                                part["functionResponse"].get("id") == current_function_id):
                                                
                                                # Replace with browser location if available
                                                if "browser" in USER_LOCATIONS and USER_LOCATIONS["browser"]:
                                                    browser_loc = USER_LOCATIONS["browser"]
                                                    
                                                    # Create a success response with browser location
                                                    new_response = {
                                                        "status": "success",
                                                        "coordinates": {
                                                            "lat": browser_loc["lat"],
                                                            "lng": browser_loc["lng"]
                                                        },
                                                        "accuracy": browser_loc.get("accuracy", 0),
                                                        "source": "browser"
                                                    }
                                                    
                                                    # Replace the response
                                                    data["content"]["parts"][part_index]["functionResponse"]["response"] = new_response
                                                    logger.info(f"Replaced get_current_place response with browser location")
                                    
                                    # Convert back to JSON and format as SSE data
                                    updated_chunk = f"data: {json.dumps(data)}\n\n"
                                    yield updated_chunk
                                except json.JSONDecodeError:
                                    # If it's not valid JSON, just pass through the original chunk
                                    yield chunk + "\n\n"
                            else:
                                # For any other format, pass through unchanged
                                yield chunk + "\n\n"
                
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

def intercept_function_calls(response_data):
    """Process API response to intercept function calls"""
    if not isinstance(response_data, list):
        return response_data
        
    for event in response_data:
        if not isinstance(event, dict) or not event.get("content") or not event["content"].get("parts"):
            continue
            
        for part_index, part in enumerate(event["content"]["parts"]):
            # Check for functionResponse from get_current_place
            if (part.get("functionResponse") and 
                part["functionResponse"].get("name") == "get_current_place"):
                
                # Replace with browser location if available
                if "browser" in USER_LOCATIONS and USER_LOCATIONS["browser"]:
                    browser_loc = USER_LOCATIONS["browser"]
                    
                    # Create a success response with browser location
                    new_response = {
                        "status": "success",
                        "coordinates": {
                            "lat": browser_loc["lat"],
                            "lng": browser_loc["lng"]
                        },
                        "accuracy": browser_loc.get("accuracy", 0),
                        "source": "browser"
                    }
                    
                    # Replace the response
                    event["content"]["parts"][part_index]["functionResponse"]["response"] = new_response
                    logger.info(f"Replaced get_current_place response with browser location")
                
    return response_data

async def cleanup_request(request_id, delay=60):
    """Clean up request data after a delay"""
    await asyncio.sleep(delay)
    if request_id in SSE_MESSAGES:
        del SSE_MESSAGES[request_id]
        logger.info(f"Cleaned up request {request_id}")