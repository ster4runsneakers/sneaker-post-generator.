import os
import time
import requests
import json
from pexelsapi.pexels import Pexels
import cloudinary
import cloudinary.uploader

# --- Configuration from Environment Variables ---
# It's assumed these are set in the Render.com environment
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SHOTSTACK_API_KEY = os.environ.get("SHOTSTACK_API_KEY")
SHOTSTACK_STAGE = "v1" # or "stage" depending on the key type

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)


# --- 1. Pexels Image Search ---
def search_images(sneaker_name: str, count: int = 5) -> list[str]:
    """Searches for sneaker images using the Pexels API."""
    if not PEXELS_API_KEY:
        raise ValueError("PEXELS_API_KEY is not set.")
    
    try:
        api = Pexels(PEXELS_API_KEY)
        search_results = api.search_photos(sneaker_name, page=1, per_page=count)
        
        image_urls = [photo.src['large'] for photo in search_results.entries]
        if not image_urls:
            print(f"Warning: No images found on Pexels for '{sneaker_name}'")
        return image_urls
    except Exception as e:
        print(f"Error fetching images from Pexels: {e}")
        return []


# --- 2. OpenAI Text Generation ---
def generate_text_for_platform(sneaker_name: str, platform: str) -> dict:
    """Generates text content for a specific social media platform using OpenAI."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set.")

    # A more sophisticated prompt
    prompt = f"""
    Create social media content for the sneaker "{sneaker_name}" specifically for the platform: {platform}.
    The tone should be exciting, modern, and engaging.
    Please provide the output in two languages, Greek and English.
    For each language, provide a 'hook' (a short, attention-grabbing opening line), a 'caption' (the main text), and a list of relevant 'hashtags'.
    Also include 2-3 relevant emojis for each language.

    Format the output strictly as a JSON object like this:
    {{
        "greek": {{
            "hook": "...",
            "caption": "...",
            "hashtags": "#...",
            "emojis": "..."
        }},
        "english": {{
            "hook": "...",
            "caption": "...",
            "hashtags": "#...",
            "emojis": "..."
        }}
    }}
    """
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        # The response from the LLM is a JSON string, so we parse it
        return {"platform": platform, **json.loads(content)}
    except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
        print(f"Error generating text for {platform}: {e}")
        # Return a fallback structure on error
        return {
            "platform": platform,
            "greek": {"hook": "Error", "caption": "Could not generate text.", "hashtags": "", "emojis": "❌"},
            "english": {"hook": "Error", "caption": "Could not generate text.", "hashtags": "", "emojis": "❌"}
        }

def generate_all_texts(sneaker_name: str, platforms: list[str]) -> list[dict]:
    """Generates text for all selected platforms."""
    return [generate_text_for_platform(sneaker_name, p) for p in platforms]


# --- 3. Shotstack Video Creation ---
def create_video(sneaker_name: str, image_urls: list[str]) -> str:
    """Creates a video from images using the Shotstack API and returns the render ID."""
    if not SHOTSTACK_API_KEY:
        raise ValueError("SHOTSTACK_API_KEY is not set.")
    if not image_urls:
        return None

    # Create video clips from image URLs
    clips = []
    for url in image_urls:
        clip = {
            "asset": {"type": "image", "src": url},
            "start": len(clips) * 2,
            "length": 2,
            "effect": "zoomIn"
        }
        clips.append(clip)

    # Add a title
    title = {
        "asset": {"type": "html", "html": f"<h1>{sneaker_name}</h1>", "css": "h1 { color: #ffffff; }"},
        "start": 0.5,
        "length": 3
    }
    
    timeline = {
        "background": "#000000",
        "tracks": [{"clips": clips}, {"clips": [title]}]
    }
    
    data = {
        "timeline": timeline,
        "output": {"format": "mp4", "resolution": "sd"}
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": SHOTSTACK_API_KEY
    }
    
    url = f"https://api.shotstack.io/{SHOTSTACK_STAGE}/render"
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["response"]["id"]
    except requests.RequestException as e:
        print(f"Error submitting video to Shotstack: {e}")
        return None

def get_render_status(render_id: str) -> dict:
    """Gets the status of a Shotstack render.""" 
    if not SHOTSTACK_API_KEY:
        raise ValueError("SHOTSTACK_API_KEY is not set.")
        
    url = f"https://api.shotstack.io/{SHOTSTACK_STAGE}/render/{render_id}"
    headers = {"x-api-key": SHOTSTACK_API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()["response"]
    except requests.RequestException as e:
        print(f"Error getting Shotstack render status: {e}")
        return {"status": "failed"}


# --- 4. Cloudinary Upload ---
def upload_to_cloudinary(video_url: str, sneaker_name: str) -> str:
    """Uploads a video from a URL to Cloudinary."""
    if not all([cloudinary.config().cloud_name, cloudinary.config().api_key, cloudinary.config().api_secret]):
        raise ValueError("Cloudinary is not configured.")
        
    try:
        upload_result = cloudinary.uploader.upload(
            video_url,
            resource_type="video",
            public_id=f"sneakers/{sneaker_name.replace(' ', '_')}_{int(time.time())}"
        )
        return upload_result.get('secure_url')
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        return None
