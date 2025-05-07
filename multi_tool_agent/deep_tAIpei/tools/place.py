import os
import requests
import googlemaps
import sys
import json
from pathlib import Path
from google.adk.agents import Agent
from google.adk.tools import ToolContext

# Path setup for imports
project_root = str(Path(__file__).parents[3])  # Go up 3 levels from current file
if project_root not in sys.path:
    sys.path.append(project_root)

# Simplified path to location file - use absolute path
LOCATION_FILE = Path("/Users/jeff/Desktop/google_agents/browser_location.json")

def get_current_place() -> dict:
    """Get the current place coordinates based on browser location"""
    try:
        # Read location from file
        if not LOCATION_FILE.exists():
            return {
                "status": "error",
                "error_message": "Location file not found"
            }
            
        with open(LOCATION_FILE, 'r') as f:
            location_data = json.load(f)
            
        if not location_data:
            return {
                "status": "error",
                "error_message": "No location data found"
            }
            
        # Get coordinates
        lat = location_data.get('lat')
        lng = location_data.get('lng')
        
        if not lat or not lng:
            return {
                "status": "error",
                "error_message": "Invalid location data"
            }
            
        return {
            "status": "success",
            "coordinates": {
                "lat": lat,
                "lng": lng
            },
        }
            
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error getting current place: {str(e)}"
        }

def get_specific_place(tool_context: ToolContext, place_name: str, query_params: dict = None) -> dict:
    """Finds information about a specific place by name using Google Maps Text Search API.
    
    This function can be used both to get coordinates for a place name and to search
    for places related to a specific location.
    
    Args:
        tool_context: The tool context containing session state
        place_name: The name of the place to find (e.g., "Taipei 101", "New York City")
        query_params: Optional additional parameters for the search query
        
    Returns:
        dict: A dictionary containing the place information with a 'status' key ('success' or 'error') 
        and either detailed results or an error message.
    """
    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return {
                "status": "error",
                "error_message": "Google Maps API key not found in environment variables."
            }
            
        url = "https://places.googleapis.com/v1/places:searchText"
        
        # Start with basic query parameters
        payload = {
            "textQuery": place_name
        }

        # Add any additional parameters provided
        if query_params:
            payload.update(query_params)
        
        # Set up the headers - request all useful fields
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.priceLevel,places.types,nextPageToken"
        }
        
        # Make the request
        response = requests.post(url, json=payload, headers=headers)
        
        # Check if the request was successful
        if response.status_code != 200:
            return {
                "status": "error",
                "error_message": f"Failed to find place: HTTP {response.status_code}, {response.text}"
            }
            
        # Parse the response
        result = response.json()
        
        # Check if any places were found
        if not result.get("places"):
            return {
                "status": "error",
                "error_message": f"No places found matching '{place_name}'."
            }
            
        # For place search, return all the places with properly formatted data
        places = []
        for place in result["places"]:
            # Extract place ID from the resource name (format: "places/PLACE_ID")
            place_id = place.get("id") or place.get("name", "").replace("places/", "")
            display_name = place.get("displayName", {}).get("text", "Unknown")
            
            place_info = {
                "name": display_name,
                "address": place.get("formattedAddress", ""),
                "rating": place.get("rating"),
                "price_level": place.get("priceLevel"),
                "types": place.get("types", []),
                'location': place.get("location", {}),
                "place_id": place_id
            }
            places.append(place_info)
        

        return {
            "status": "success",
            "results": places,
            "next_page_token": result.get("nextPageToken")
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An error occurred while finding information for '{place_name}': {str(e)}"
        }

def store_place_data(places: list, tool_context: ToolContext = None) -> list:
    """Store place ID and name pairs in tool context and return the formatted list.
    
    This is a helper function used by find_places_nearby to extract and store
    place information for use by other functions.
    
    Args:
        places: List of place dictionaries containing at least "place_id" and "name" keys
        tool_context: The tool context for storing state
        
    Returns:
        list: List of tuples containing (place_id, place_name) pairs
    """
    if not places:
        return []
        
    place_tuples = []
    
    # Extract place ID and name pairs
    for place in places:
        place_id = place.get("place_id")
        name = place.get("name")
        
        if place_id and name:
            place_tuples.append((place_id, name))
    
    # Store in tool context if provided
    if tool_context and place_tuples:
        # Get existing places or initialize with empty list
        existing_places = tool_context.state.get("places", [])
        # Append new place tuples to existing ones
        tool_context.state["places"] = existing_places + place_tuples
        
    return place_tuples

def _get_places_by_coordinates(coordinates, search_params):
    """Helper function to search for places by coordinates using Places Nearby API.
    
    This function makes a request to the Google Places Nearby API using the provided
    coordinates and search parameters. It processes the API response and formats the
    results into a consistent structure.
    
    Args:
        coordinates: Dictionary with lat/lng keys representing the center point for the search
        search_params: Dictionary with search parameters including radius, keyword, types, etc.
        
    Returns:
        tuple: Contains three elements:
            - status_code: "success" or "error"
            - places_list: List of place dictionaries or error message string if status is "error"
            - next_page_token: Token for pagination or None if no more results
    """
    try:
        gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
        results = gmaps.places_nearby(
            location=coordinates,
            **search_params
        )
        
        if results and results["status"] == "OK":
            places = []
            for place in results["results"]:
                place_info = {
                    "name": place.get("name"),
                    "address": place.get("vicinity"),
                    "rating": place.get("rating"),
                    "price_level": place.get("price_level"),
                    "types": place.get("types", []),
                    "place_id": place.get("place_id")
                }
                places.append(place_info)
            
            return "success", places, results.get("next_page_token")
        else:
            return "error", f"No places found. Status: {results.get('status')}", None
    except Exception as e:
        return "error", f"API error: {str(e)}", None

def _prepare_search_params(radius, keyword, language, min_price, max_price, name, open_now, rank_by, type, page_token):
    """Prepare search parameters for Places API.
    
    This function takes individual search parameters and organizes them into a properly
    formatted dictionary for use with the Google Places API. It filters out None values
    and empty strings to ensure a clean parameter set.
    
    Args:
        radius: Distance in meters within which to search
        keyword: Term to match against place content
        language: Language code for results (e.g., "en" for English)
        min_price: Minimum price level (0-4)
        max_price: Maximum price level (0-4)
        name: Terms to match against place names
        open_now: Boolean for returning only places that are currently open
        rank_by: Method for ranking results ("prominence" or "distance")
        type: Specific place type to filter results
        page_token: Token for retrieving next page of results
        
    Returns:
        dict: Parameters ready for API call with all None and empty values removed
    """
    params = {
        "radius": radius,
        "keyword": keyword,
        "language": language,
        "min_price": min_price,
        "max_price": max_price,
        "open_now": open_now,
        "rank_by": rank_by,
        "page_token": page_token,
    }
    
    if name:
        params["name"] = name
    
    if type:
        params["type"] = type
        
    # Remove None values and empty strings
    return {k: v for k, v in params.items() if v or v == 0}

def _convert_price_levels(min_price, max_price):
    """Convert numeric price levels to Google's format.
    
    This function translates the 0-4 price level range used in the function parameters
    to the string format expected by the Google Places API (Text Search).
    
    Args:
        min_price: Minimum price level (0-4)
            0: Free
            1: Inexpensive
            2: Moderate
            3: Expensive
            4: Very Expensive
        max_price: Maximum price level (0-4)
        
    Returns:
        list: List of Google's price level string identifiers within the specified range
              Returns empty list if default range (0-4) is specified
    """
    if min_price == 0 and max_price == 4:
        return []  # Default range, no need to specify
        
    price_level_map = {
        0: "PRICE_LEVEL_FREE",
        1: "PRICE_LEVEL_INEXPENSIVE", 
        2: "PRICE_LEVEL_MODERATE",
        3: "PRICE_LEVEL_EXPENSIVE",
        4: "PRICE_LEVEL_VERY_EXPENSIVE"
    }
    
    price_levels = []
    for i in range(min_price, max_price + 1):
        if i in price_level_map:
            price_levels.append(price_level_map[i])
            
    return price_levels

def find_places_nearby(
    location: str = "current_location",
    radius: int = 5000,  # Increased from 1000 to 2000 meters for more comprehensive results
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
    
    This function can search for places using two different approaches:
    1. Using the device's current location with the Places Nearby API
    2. Using a named location (e.g., "Taipei 101") with the Places Text Search API
    
    Results from either approach are stored in the tool context for later reference by
    other functions like get_place_details() and show_place_details().

    Args:
        location: String indicating location to use. 
                 Use "current_location" to use device's current location,
                 or provide a place name like "Taipei 101" or "New York City".
        radius: Distance in meters within which to search (default: 2000)
        keyword: A term to match against place content
        language: The language for results (default: "en")
        min_price: Minimum price level (0-4)
            0: Free
            1: Inexpensive
            2: Moderate
            3: Expensive
            4: Very Expensive
        max_price: Maximum price level (0-4)
        name: One or more terms to match against place names
        open_now: Whether to return only places open now
        rank_by: How to rank results ('prominence' or 'distance')
        type: Restrict results to specific place types
        page_token: Token for pagination
        tool_context: The ADK tool context for storing place information

    Returns:
        dict: A dictionary containing the search results with:
            - 'status': 'success' or 'error'
            - 'results': List of places if successful, with each place containing:
                * name: The place name
                * address: The formatted address or vicinity
                * rating: The average rating (0.0-5.0)
                * price_level: The price level (0-4)
                * types: List of place type categories
                * place_id: The Google Places unique identifier
            - 'next_page_token': Token for retrieving the next page of results
            - 'error_message': Description of the error if status is 'error'
            
        Also stores tuples of (place_id, place_name) in tool_context.state["places"] for
        later reference by other functions like get_place_details().
    """
    try:
        # Prepare common search parameters
        search_params = _prepare_search_params(
            radius, keyword, language, min_price, max_price, 
            name, open_now, rank_by, type, page_token
        )
        
        status = "error"
        places = []
        next_page_token = None
        error_message = ""
        
        # Branch based on location parameter
        if location == "current_location":
            # Get current location coordinates
            current_place = get_current_place()
            if current_place["status"] == "error":
                return {
                    "status": "error",
                    "error_message": f"Could not determine current location: {current_place['error_message']}"
                }
            
            # Extract coordinates from the response
            coordinates = current_place["coordinates"]
            
            # Search for places near coordinates
            status, result, next_page_token = _get_places_by_coordinates(
                coordinates, 
                search_params
            )
            
            if status == "success":
                places = result
            else:
                error_message = f"No places found near your current location. {result}"
                
        else:
            # Build text search query
            query = location
            if keyword:
                query = f"{keyword} in {location}"
            if name:
                query = f"{name} {query}"
                
            # Prepare query parameters for text search
            query_params = {
                "languageCode": language,
                "openNow": open_now
            }
            
            # Add price levels if specified
            price_levels = _convert_price_levels(min_price, max_price)
            if price_levels:
                query_params["priceLevels"] = price_levels
            
            # Add type and page token if specified
            if type:
                query_params["includedType"] = type
            if page_token:
                query_params["pageToken"] = page_token
            
            # Perform the text search
            place_result = get_specific_place(tool_context, query, query_params)
            
            # Process results
            if place_result["status"] == "success":
                places = place_result["results"]
                next_page_token = place_result.get("next_page_token")
                status = "success"
            else:
                error_message = place_result.get("error_message", "No places found matching your criteria.")
        
        # Format and return the response
        if status == "success" and places:
            # Store place data in tool context
            store_place_data(places, tool_context)
            
            return {
                "status": "success",
                "results": places,
                "next_page_token": next_page_token
            }
        else:
            return {
                "status": "error", 
                "error_message": error_message or "No places found matching your criteria."
            }

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An error occurred while finding nearby places: {str(e)}"
        }

def search_places(
    query: str = "",
    location: str = "current_location",
    radius: int = 3000,  # Larger radius for more comprehensive results
    open_now: bool = False,
    tool_context: ToolContext = None,
) -> dict:
    """Simple wrapper for find_places_nearby with minimal parameters for ease of use.
    
    This function provides a simpler interface to the more comprehensive find_places_nearby
    function, requiring fewer parameters for quick searches. It automatically uses the
    most comprehensive settings to get detailed results.
    
    Args:
        query: Search term for what you're looking for (e.g., "coffee", "restaurants")
        location: Either "current_location" or a place name (e.g., "Taipei 101")
        radius: Search radius in meters (default: 3000)
        open_now: Whether to only show currently open places (default: False)
        tool_context: The ADK tool context for storing place information
        
    Returns:
        dict: Same format as find_places_nearby
    """
    # Use the more comprehensive function with our simplified parameters
    return find_places_nearby(
        location=location,
        radius=radius,
        keyword=query,
        open_now=open_now,
        tool_context=tool_context,
        # Use all defaults for other parameters to get comprehensive results
    )

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
        # Validate place_name parameter
        if not place_name or not place_name.strip():
            return {
                "status": "error",
                "error_message": "Place name cannot be empty. Please provide a specific place name."
            }
            
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
            # Check for partial matches if exact match fails
            closest_match = None
            closest_similarity = 0
            
            for pid, pname in tool_context.state["places"]:
                # Simple similarity check - can be enhanced with more sophisticated algorithms
                if place_name.lower() in pname.lower() or pname.lower() in place_name.lower():
                    similarity = len(set(place_name.lower()) & set(pname.lower())) / len(set(place_name.lower()) | set(pname.lower()))
                    if similarity > closest_similarity:
                        closest_similarity = similarity
                        closest_match = (pid, pname)
            
            if closest_match and closest_similarity > 0.5:  # Threshold for accepting a partial match
                place_id = closest_match[0]
                place_name = closest_match[1]  # Update to the matched name
            else:
                # List available places to help the user
                available_places = [pname for _, pname in tool_context.state["places"]]
                return {
                    "status": "error",
                    "error_message": f"Place '{place_name}' not found in stored places. Available places: {', '.join(available_places[:5])}{'...' if len(available_places) > 5 else ''}"
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

def show_place_details(
    place_id: str = "",
    place_name: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """Prepares place details for display on a map in the web interface.
    
    This function retrieves detailed place information and formats it for
    display in the web UI. It returns a structured response that can be
    used by the frontend to render a map with place details.
    
    Args:
        place_id: The Google Maps place ID. If provided, this takes precedence.
        place_name: The name of the place to show. Used to look up place_id if not provided directly.
        tool_context: The ADK tool context containing stored place information.
        
    Returns:
        dict: A dictionary containing the place details with a 'status' key ('success' or 'error'),
        'place_id', 'name', 'location' (lat/lng), and other details if successful,
        or an 'error_message' if an error occurred.
    """
    try:
        # If place_id is not provided directly, try to find it from place_name
        if not place_id and place_name:
            if not tool_context or "places" not in tool_context.state:
                return {
                    "status": "error",
                    "error_message": "No places found in memory. Please search for places first."
                }
                
            # Find the place_id for the given place_name
            for pid, pname in tool_context.state["places"]:
                if pname.lower() == place_name.lower():
                    place_id = pid
                    break
                    
        if not place_id:
            return {
                "status": "error",
                "error_message": f"Could not find place ID for '{place_name}'. Please provide a valid place."
            }
            
        # Get the place details using the existing get_place_details function
        # We'll request only valid fields needed for a good map display
        fields = [
            "name", "formatted_address", "geometry", "rating",  
            "opening_hours", "website", "formatted_phone_number", 
            "price_level", "photo"
        ]
        
        gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
        place_details = gmaps.place(
            place_id=place_id,
            fields=fields,
            language="en"
        )
        
        if place_details and place_details.get("status") == "OK":
            result = place_details.get("result", {})
            
            # Extract and format the location data
            location = None
            if "geometry" in result and "location" in result["geometry"]:
                location = {
                    "lat": float(result["geometry"]["location"]["lat"]),
                    "lng": float(result["geometry"]["location"]["lng"])
                }
                
            # Process photos if available
            photos = []
            if "photos" in result:
                for photo in result["photos"][:3]:  # Limit to 3 photos
                    if "photo_reference" in photo:
                        photos.append(photo["photo_reference"])
            
            # Return a structured response suitable for map display
            return {
                "status": "success",
                "place_id": place_id,
                "name": result.get("name", ""),
                "address": result.get("formatted_address", ""),
                "location": location,
                "rating": result.get("rating"),
                "types": result.get("type", []),  # Changed from 'types' to 'type'
                "opening_hours": result.get("opening_hours", {}),
                "website": result.get("website", ""),
                "phone": result.get("formatted_phone_number", ""),
                "price_level": result.get("price_level"),
                "photos": photos,
                "action": "show_on_map"  # Signal to the frontend to display this on a map
            }
        else:
            return {
                "status": "error",
                "error_message": f"Failed to get place details. Status: {place_details.get('status')}"
            }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An error occurred while preparing place details for display: {str(e)}"
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
                "rating, and price level. "
                "When a user wants to see more details about a specific place, "
                "use the 'show_place_details' tool to display it on a map.",
    tools=[find_places_nearby, get_place_details, show_place_details],
)