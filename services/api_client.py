import json
import os
import requests
from config.settings import API_BASE_URL, get_api_headers


def get_prompt_ai():
    """Load AI prompt from local file."""
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_path = os.path.join(current_dir, "config", "prompt_ai.json")
    with open(prompt_path, "r", encoding="utf-8") as f:
        local_prompts = json.load(f)
    print("Using local prompt")
    return local_prompts["default_system_message"]


def fetch_screening_data():
    """Fetch pending screening data from the recruitment API."""
    url = f"{API_BASE_URL}/api/screening-ai"
    headers = get_api_headers()

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            print("Successfully fetched screening data from API")
            return response.json()
        else:
            return {
                "error": f"Request failed with status code: {response.status_code}",
                "message": response.text,
            }
    except requests.exceptions.RequestException as e:
        return {"error": "Request failed", "message": str(e)}


def fetch_screening_by_socket(job_id, user_id):
    """Fetch screening data for a specific job/user from socket endpoint."""
    url = f"{API_BASE_URL}/api/screening-ai-socket"
    headers = get_api_headers()
    params = {"jobId": job_id, "userId": user_id}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API request failed: {response.status_code}")
            print(f"Error message: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Network error: {str(e)}")
        return None


def report_screening_failed(screening_id, error):
    """Report a failed screening to the API so it can be marked 'Gagal'."""
    url = f"{API_BASE_URL}/api/screening-ai-failed"
    headers = {
        "Authorization": get_api_headers()["Authorization"],
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            url,
            json={"screening_id": screening_id, "error": str(error)[:500]},
            headers=headers,
            timeout=30,
        )
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Failed to report screening failure: {e}")
        return False


def send_screening_result(formatted_data):
    """Send formatted screening result to the API."""
    url = os.getenv("API_ENDPOINT", f"{API_BASE_URL}/api/result-screening-ai")
    headers = {
        "Authorization": get_api_headers()["Authorization"],
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=formatted_data, headers=headers, timeout=30)
        return response.status_code == 200, response.text
    except Exception as e:
        print(f"Error sending to API: {str(e)}")
        return False, str(e)
