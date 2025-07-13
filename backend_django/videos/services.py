import requests
from django.conf import settings

RUNWAY_API_BASE_URL = "https://api.dev.runwayml.com/v1"
RUNWAY_API_KEY = settings.RUNWAY_API_KEY
RUNWAY_API_VERSION = "2024-11-06"  # API version from docs

# NOTE: Replace these with your actual model IDs from your Runway account.
TEXT_TO_IMAGE_MODEL_ID = "gen4_image"
IMAGE_TO_VIDEO_MODEL_ID = "gen4_turbo"

def start_text_to_image_task(prompt: str):
    """Starts a text-to-image generation task."""
    url = f"{RUNWAY_API_BASE_URL}/text_to_image" # Changed endpoint
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type": "application/json",
        "X-Runway-Version": RUNWAY_API_VERSION,
    }
    payload = {
        "model": TEXT_TO_IMAGE_MODEL_ID,
        "promptText": prompt,
        "ratio": "1920:1080"
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def start_image_to_video_task(image_url: str):
    """Starts an image-to-video generation task."""
    url = f"{RUNWAY_API_BASE_URL}/image_to_video" # Changed endpoint
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type": "application/json",
        "X-Runway-Version": RUNWAY_API_VERSION,
    }
    payload = {
        "model": IMAGE_TO_VIDEO_MODEL_ID,
        "promptImage": image_url,
        "ratio": "1280:720"
        # You can add other parameters like motion, seed, etc.
        # "motion": 5,
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def get_task_status(task_id: str):
    """Retrieves the status of a specific generation task."""
    url = f"{RUNWAY_API_BASE_URL}/tasks/{task_id}"
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "X-Runway-Version": RUNWAY_API_VERSION,
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
