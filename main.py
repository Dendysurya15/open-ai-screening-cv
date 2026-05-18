"""
CV Screening AI - Automated candidate evaluation using Ollama LLM.

This application:
1. Fetches pending screening data from the recruitment API
2. Listens for real-time events via Pusher
3. Evaluates candidates using a local Ollama AI model
4. Sends results back to the API
"""

from services.scheduler import start_application


if __name__ == "__main__":
    try:
        start_application()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"\nApplication error: {str(e)}")
    finally:
        print("Application stopped")
