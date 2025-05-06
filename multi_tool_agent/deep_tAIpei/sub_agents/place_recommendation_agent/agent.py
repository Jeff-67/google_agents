from google.adk.agents import Agent
import logging
from typing import Optional, Dict, Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest
from google.genai import types
from google import genai
from google.genai.types import HttpOptions

from deep_tAIpei.tools.place import find_places_nearby, get_place_details, show_place_details, get_current_place
from deep_tAIpei.shared_libraries.constants import FAST_GEMINI_MODEL
from deep_tAIpei.sub_agents.place_recommendation_agent.prompt import PLACE_RECOMMENDATION_AGENT_INSTRUCTION

# Storage for LLM requests (key: agent_name)
STORED_REQUESTS: Dict[str, LlmRequest] = {}

def store_request(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """Before model callback that stores the LLM request for potential retries.
    
    This callback is called before the model is invoked. It stores the request
    so we can access it in the after_model_callback if we need to retry.
    """
    logger = logging.getLogger(__name__)
    
    # Store the request using the agent name as key
    agent_name = callback_context.agent_name
    logger.info(f"Storing LLM request for agent: {agent_name}")
    STORED_REQUESTS[agent_name] = llm_request
    
    # Continue with normal processing (don't skip the model call)
    return None

def handle_empty_response(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """After model callback to handle empty model responses with retry mechanism.
    
    When an empty response is detected, it uses the stored request (captured
    in the before_model_callback) to retry up to 3 times.
    """
    logger = logging.getLogger(__name__)
    
    # Check if we have an empty response
    if not llm_response or not llm_response.content or not llm_response.content.parts or len(llm_response.content.parts) == 0:
        logger.warning("Completely missing response detected")
    else:
        # Check if any parts contain function_call or text
        for part in llm_response.content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                # Response has a function call - not empty!
                logger.info("Response contains a function call, not considered empty")
                return None
            if hasattr(part, 'text') and part.text and part.text.strip():
                # Response has non-empty text - not empty!
                return None
                
        logger.warning("Response has parts but no function_call or non-empty text")
    
    # We have an empty response
    logger.warning("Empty model response detected in after_model_callback")
    
    # Get the agent name to retrieve the stored request
    agent_name = callback_context.agent_name
    
    # Get the stored request
    llm_request = STORED_REQUESTS.get(agent_name)
    if not llm_request:
        logger.error(f"Cannot retry - no stored request for agent: {agent_name}")
        return LlmResponse(
            content=types.Content(
                role="model", 
                parts=[types.Part(text="I'm having trouble processing your request. Please try again.")]
            )
        )
    
    # Simple retry implementation - try up to 3 times
    MAX_RETRIES = 3
    
    for retry_count in range(1, MAX_RETRIES + 1):
        logger.info(f"Retry attempt {retry_count}/{MAX_RETRIES}")
        
        try:
            # Create the Gemini client with API version specified
            client = genai.Client(http_options=HttpOptions(api_version="v1"))
            
            # Log the contents for debugging
            logger.info(f"Retry request contents: {llm_request.contents}")
            
            # Call the model with the original request parameters directly
            retry_response = client.models.generate_content(
                model=llm_request.model,
                contents=llm_request.contents,
                config=llm_request.config
            )
            
            # Check if retry successful - now properly handle function_call responses
            if retry_response:
                if hasattr(retry_response, 'candidates') and retry_response.candidates:
                    candidate = retry_response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content:
                        parts = candidate.content.parts
                        if parts:
                            for part in parts:
                                if (hasattr(part, 'function_call') and part.function_call) or \
                                   (hasattr(part, 'text') and part.text and part.text.strip()):
                                    # We have a valid response with either function_call or non-empty text
                                    logger.info(f"Retry successful on attempt {retry_count}")
                                    return LlmResponse.create(retry_response)
            
            logger.warning(f"Retry attempt {retry_count} also returned empty response")
                
        except Exception as e:
            logger.error(f"Error during retry attempt {retry_count}: {str(e)}")
    
    # All retries failed, return fallback message
    logger.warning(f"All {MAX_RETRIES} retry attempts failed, returning fallback message")
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    text="I'm sorry, I'm having trouble providing information about places at the moment. "
                         "Please try a more specific question about locations you're interested in."
                )
            ]
        )
    )

# Create the agent with both callbacks
place_recommendation_agent = Agent(
    name="place_recommendation_agent",
    model=FAST_GEMINI_MODEL,
    description="Agent to handle place recommendations and detailed information flow.",
    instruction=PLACE_RECOMMENDATION_AGENT_INSTRUCTION,
    tools=[find_places_nearby, get_place_details, show_place_details, get_current_place],
    before_model_callback=store_request,
    after_model_callback=handle_empty_response
) 