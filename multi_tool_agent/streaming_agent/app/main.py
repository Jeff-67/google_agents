from pathlib import Path
from fastapi import FastAPI, Request, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging
import asyncio
import json
import uuid
import os
import re
import dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from the deep_tAIpei/.env file
project_root = Path(__file__).parents[3]  # Go up 3 levels from app/main.py
env_path = project_root / "multi_tool_agent" / "deep_tAIpei" / ".env"
logger.info(f"Looking for .env file at {env_path}")
if env_path.exists():
    dotenv.load_dotenv(dotenv_path=env_path)
    logger.info(f"Loaded environment variables from {env_path}")
    
    # Debug: Check if we got the API key
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")

else:
    logger.warning(f"Could not find .env file at {env_path}")
    
    # Try an alternative path
    alt_env_path = project_root / "deep_tAIpei" / ".env"
    logger.info(f"Trying alternative .env path: {alt_env_path}")
    if alt_env_path.exists():
        dotenv.load_dotenv(dotenv_path=alt_env_path)
        logger.info(f"Loaded environment variables from alternative path {alt_env_path}")
        
        # Debug: Check if we got the API key
        api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
        if api_key:
            masked_key = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:] if len(api_key) > 8 else "****"
            logger.info(f"Successfully loaded Google Maps API key from alternative path: {masked_key}")
        else:
            logger.error("API key was NOT loaded correctly from alternative path - GOOGLE_MAPS_API_KEY is empty")

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
    """Serves the index.html with Google Maps API key injected"""
    # Get the Google Maps API key from environment
    google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    
    # Log API key information (safely)
    if google_maps_api_key:
        masked_key = google_maps_api_key[:4] + "*" * (len(google_maps_api_key) - 8) + google_maps_api_key[-4:] if len(google_maps_api_key) > 8 else "****"
        logger.info(f"Using Google Maps API key: {masked_key}")
    else:
        # List all environment variables that might contain the API key
        potential_keys = [k for k in os.environ.keys() if 'API' in k or 'KEY' in k or 'GOOGLE' in k or 'MAP' in k]
        logger.warning(f"No GOOGLE_MAPS_API_KEY found. Potential key variables: {potential_keys}")
    
    # Read the index.html file
    index_path = STATIC_DIR / "index.html"
    try:
        with open(index_path, "r") as f:
            html_content = f.read()
            
        # Replace the placeholder with the actual API key
        if google_maps_api_key:
            # Check if the placeholder exists in the HTML
            if "YOUR_API_KEY" in html_content:
                original_html = html_content
                html_content = html_content.replace("YOUR_API_KEY", google_maps_api_key)
                
                # Verify replacement worked
                if html_content != original_html:
                    logger.info("Successfully injected Google Maps API key into index.html")
                else:
                    logger.warning("Failed to inject API key - no replacement occurred")
            else:
                logger.warning("Could not find 'YOUR_API_KEY' placeholder in index.html")
        else:
            logger.warning("No Google Maps API key found in environment variables")
            
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Error reading index.html: {str(e)}")
        return FileResponse(index_path)  # Fallback to normal file serving

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
                                            elif (function_call_detected and 
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
                                            
                                            # Check for functionResponse from show_place_details
                                            elif (part.get("functionResponse") and 
                                                part["functionResponse"].get("name") == "show_place_details"):
                                                
                                                # Get the original response
                                                response = part["functionResponse"].get("response", {})
                                                logger.info(f"Received show_place_details response: {response}")
                                                
                                                # If status is success and we have location data
                                                if response.get("status") == "success" and response.get("location"):
                                                    # Add a flag to indicate that this should trigger a map display in the frontend
                                                    # We don't modify the actual data, just add the UI action flag
                                                    response["ui_action"] = "show_map"
                                                    
                                                    # Log location data structure
                                                    location = response.get("location", {})
                                                    logger.info(f"Location data for map: lat={location.get('lat')}, lng={location.get('lng')}")
                                                    
                                                    # Replace the response
                                                    data["content"]["parts"][part_index]["functionResponse"]["response"] = response
                                                    logger.info(f"Enhanced show_place_details response for UI rendering")
                                                else:
                                                    # Log the issue with the response
                                                    logger.warning(f"Invalid show_place_details response: status={response.get('status')}, location={response.get('location')}")
                                    
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
            
            # Check for functionResponse from show_place_details
            elif (part.get("functionResponse") and 
                  part["functionResponse"].get("name") == "show_place_details"):
                
                # Get the original response
                response = part["functionResponse"].get("response", {})
                logger.info(f"Received show_place_details response: {response}")
                
                # If status is success and we have location data
                if response.get("status") == "success" and response.get("location"):
                    # Add a flag to indicate that this should trigger a map display in the frontend
                    # We don't modify the actual data, just add the UI action flag
                    response["ui_action"] = "show_map"
                    
                    # Log location data structure
                    location = response.get("location", {})
                    logger.info(f"Location data for map: lat={location.get('lat')}, lng={location.get('lng')}")
                    
                    # Replace the response
                    event["content"]["parts"][part_index]["functionResponse"]["response"] = response
                    logger.info(f"Enhanced show_place_details response for UI rendering")
                else:
                    # Log the issue with the response
                    logger.warning(f"Invalid show_place_details response: status={response.get('status')}, location={response.get('location')}")
                
    return response_data

async def cleanup_request(request_id, delay=60):
    """Clean up request data after a delay"""
    await asyncio.sleep(delay)
    if request_id in SSE_MESSAGES:
        del SSE_MESSAGES[request_id]
        logger.info(f"Cleaned up request {request_id}")