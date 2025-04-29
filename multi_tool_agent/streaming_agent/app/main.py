from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

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
    """Proxy for run endpoint"""
    try:
        json_data = await request.json()
        logger.info(f"Proxying run request for {json_data.get('app_name')}/{json_data.get('session_id')}")
        
        # Use a much longer timeout for the run endpoint since it can take a while
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