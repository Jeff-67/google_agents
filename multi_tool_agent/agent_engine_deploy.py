import os
import vertexai
from vertexai import agent_engines
from dotenv import load_dotenv
from deep_tAIpei.agent import root_agent

# Load environment variables from .env file
load_dotenv()

# Initialize Vertex AI with project details
vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
    staging_bucket=os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET"),
)

# Define required packages for deployment
requirements = [
    "google-cloud-aiplatform[agent_engines,adk]>=1.38.0",
    "python-dotenv",
    "googlemaps",
    "fastapi",
    "uvicorn",
    "httpx",
    "requests",
    "pathlib",
]

# Include local packages needed for the agent
extra_packages = ["deep_tAIpei"]

# Optional: Create a unique directory name to avoid overwrites
# gcs_dir_name = str(uuid.uuid4())
gcs_dir_name = "deep_taipei_agent"  # Or use a fixed name if you prefer

# Add metadata for better organization in Vertex AI
display_name = "Deep tAIpei Agent"
description = """
A Taipei food and bar discovery assistant using multiple sub-agents to provide
recommendations based on weather, location, and user preferences.
"""

# Environment variables that the agent needs
env_vars = {
    "GOOGLE_MAPS_API_KEY": os.getenv("GOOGLE_MAPS_API_KEY"),
    # Add any other environment variables your agent needs
}

# Deploy the agent to Vertex AI Agent Engine
try:
    print("Deploying agent to Vertex AI Agent Engine...")
    remote_app = agent_engines.create(
        agent_engine=root_agent,
        requirements=requirements,
        extra_packages=extra_packages,
        gcs_dir_name=gcs_dir_name,
        display_name=display_name,
        description=description,
        env_vars=env_vars
    )
    print(f"Agent deployed successfully!")
    print(f"Resource name: {remote_app.resource_name}")
except Exception as e:
    print(f"Error deploying agent: {e}") 