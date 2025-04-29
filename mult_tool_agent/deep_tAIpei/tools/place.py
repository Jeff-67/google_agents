import os
import googlemaps
from google.adk.agents import Agent
from google.adk.tools import ToolContext

def get_current_place(source: str = "device") -> dict:
    """Finds the current place using the Google Maps Geolocation API.
    
    This function can determine location from different sources:
    - "device": Uses the device's cell tower and WiFi information (requires client-side execution)
    - "server": Uses the server's IP address (less accurate for end users)
    - "browser": Uses the browser's IP address (requires client-side execution)
    - "auto": Tries device first, then falls back to IP-based location

    Args:
        source: Where to get the location from. One of: "device", "server", "browser", "auto"
               Defaults to "device" for most accurate results.

    Returns:
        dict: A dictionary containing the place information with a 'status' key ('success' or 'error') 
        and a 'coordinates' key with lat/lng if successful, or an 'error_message' if an error occurred.
    """
    try:
        gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
        
        # Prepare the geolocation request parameters
        geolocation_params = {
            "consider_ip": True  # Always use IP as fallback since we don't have device data
        }

        try:
            # Try to get location using geolocation
            geolocation_result = gmaps.geolocate(**geolocation_params)
            
            if not geolocation_result or "location" not in geolocation_result:
                return {
                    "status": "error",
                    "error_message": f"Could not determine current location from {source}."
                }
                
            # Get the coordinates and accuracy from geolocation result
            location = geolocation_result["location"]
            accuracy = geolocation_result.get("accuracy", 0)  # Default to 0 if not provided
            
            return {
                "status": "success",
                "coordinates": {
                    "lat": location["lat"],
                    "lng": location["lng"]
                },
                "accuracy": accuracy,
                "source": source
            }
        except Exception as e:
            if "INVALID_REQUEST" in str(e):
                return {
                    "status": "error",
                    "error_message": "Could not determine location. The request was invalid. This might be because the API key doesn't have the required permissions or the request format was incorrect."
                }
            raise e
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An error occurred while finding the current place: {str(e)}"
        }

def find_places_nearby(
    location: dict = {},  # Empty dict will trigger current location lookup
    radius: int = 1000,  # Default to 1km radius
    keyword: str = "",
    language: str = "en",
    min_price: int = 0,
    max_price: int = 4,
    name: str = "",
    open_now: bool = False,
    rank_by: str = "prominence",
    type: str = "",
    page_token: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """Finds nearby places using the Google Maps Places API and stores place information in memory.

    Args:
        location: Optional latitude/longitude value for which to find nearby places.
                 If empty dict is provided, will use current location.
        radius: Distance in meters within which to search (default: 1000)
        keyword: A term to match against place content
        language: The language for results (default: "en")
        min_price: Minimum price level (0-4)
        max_price: Maximum price level (0-4)
        name: One or more terms to match against place names
        open_now: Whether to return only places open now
        rank_by: How to rank results ('prominence' or 'distance')
        type: Restrict results to specific place types
        page_token: Token for pagination
        tool_context: The ADK tool context for storing place information

    Returns:
        dict: A dictionary containing the search results with a 'status' key ('success' or 'error') 
        and a 'results' key with the places if successful, or an 'error_message' if an error occurred.
        Each place in results includes basic info (name, address, rating, price_level, types, place_id).
        Also stores tuples of (place_id, place_name) in tool_context.state["places"] for later reference.
    """
    try:
        # If location is empty, get current location
        if not location:
            current_place = get_current_place()
            if current_place["status"] == "error":
                return {
                    "status": "error",
                    "error_message": f"Could not determine current location: {current_place['error_message']}"
                }
            # Use the coordinates from the current_place response
            location = current_place["coordinates"]

        gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
        results = gmaps.places_nearby(
            location=location,
            radius=radius,
            keyword=keyword,
            language=language,
            min_price=min_price,
            max_price=max_price,
            name=name,
            open_now=open_now,
            rank_by=rank_by,
            type=type,
            page_token=page_token,
        )

        if results and results["status"] == "OK":
            places = []
            place_tuples = []  # List to store (place_id, place_name) tuples
            
            for place in results["results"]:
                # Get basic place info
                place_info = {
                    "name": place.get("name"),
                    "address": place.get("vicinity"),
                    "rating": place.get("rating"),
                    "price_level": place.get("price_level"),
                    "types": place.get("types", []),
                    "place_id": place.get("place_id")
                }
                places.append(place_info)
                
                # Store tuple for later reference
                if place_info["place_id"] and place_info["name"]:
                    place_tuples.append((place_info["place_id"], place_info["name"]))

            # Store place tuples in tool context
            if tool_context:
                tool_context.state["places"] = place_tuples

            return {
                "status": "success",
                "results": places,
                "next_page_token": results.get("next_page_token")
            }
        else:
            return {
                "status": "error",
                "error_message": f"No places found. Status: {results.get('status')}"
            }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An error occurred while finding nearby places: {str(e)}"
        }

def get_place_details(
    place_name: str,
    fields: list[str] = [],  # Empty list as default instead of None
    language: str = "en",
    reviews_no_translations: bool = False,
    reviews_sort: str = "most_relevant",
    tool_context: ToolContext = None,
) -> dict:
    """Get comprehensive details for a place using the Google Places API.

    Args:
        place_name: The name of the place to get details for.
        fields: The fields specifying the types of place data to return.
               If empty list, returns all available fields.
        language: The language in which to return results (default: "en").
        reviews_no_translations: Whether to disable translation of reviews.
        reviews_sort: The sorting method to use when returning reviews.
                     Can be "most_relevant" (default) or "newest".
        tool_context: The ADK tool context containing stored place information.

    Returns:
        dict: A dictionary containing the place details with a 'status' key ('success' or 'error')
        and a 'result' key with the place details if successful, or an 'error_message' if an error occurred.
    """
    try:
        if not tool_context or "places" not in tool_context.state:
            return {
                "status": "error",
                "error_message": "No places found in memory. Please search for places first."
            }

        # Find the place_id for the given place_name
        place_id = None
        for pid, pname in tool_context.state["places"]:
            if pname.lower() == place_name.lower():
                place_id = pid
                break

        if not place_id:
            return {
                "status": "error",
                "error_message": f"Place '{place_name}' not found in stored places."
            }

        gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
        place_details = gmaps.place(
            place_id=place_id,
            fields=fields,
            language=language,
            reviews_no_translations=reviews_no_translations,
            reviews_sort=reviews_sort
        )

        if place_details and place_details.get("status") == "OK":
            return {
                "status": "success",
                "result": place_details.get("result", {}),
                "html_attributions": place_details.get("html_attributions", [])
            }
        else:
            return {
                "status": "error",
                "error_message": f"Failed to get place details. Status: {place_details.get('status')}"
            }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An error occurred while getting place details: {str(e)}"
        }

find_places_nearby_agent = Agent(
    name="find_places_nearby_agent",
    model="gemini-2.0-flash-001",
    description="Agent to find nearby places using Google Maps.",
    instruction="You are a helpful places assistant. "
                "When the user asks for nearby places, "
                "use the 'find_places_nearby' tool to search for places. "
                "You can filter results by location, radius, keyword, type, "
                "price level, and other parameters. "
                "If the tool returns an error, inform the user politely. "
                "If the tool is successful, present the places in a clear, "
                "organized manner with relevant details like name, address, "
                "rating, and price level.",
    tools=[find_places_nearby],
)