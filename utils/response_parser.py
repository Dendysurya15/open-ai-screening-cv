import json
from datetime import datetime


def _find_candidates_in_dict(data, depth=0):
    """Recursively search for 'candidates' key in nested dicts (max depth 3)."""
    if depth > 3 or not isinstance(data, dict):
        return None
    if "candidates" in data:
        return data
    for value in data.values():
        found = _find_candidates_in_dict(value, depth + 1)
        if found is not None:
            return found
    return None


def _validate_and_extract(result):
    """
    Try to extract a valid {lowongan_id, candidates} dict from the parsed JSON.
    Handles cases where the model wraps the output in extra keys.
    Returns the valid dict or raises ValueError.
    """
    if not isinstance(result, dict):
        raise ValueError("Response must be a JSON object")

    # Happy path: model returned correct top-level structure
    if "candidates" in result or "lowongan_id" in result:
        return result

    # Fallback: model wrapped output in extra keys (e.g. root_fields, data)
    found = _find_candidates_in_dict(result)
    if found is not None:
        print(f"\n⚠ Model wrapped output — unwrapped from nested keys. Top-level keys were: {list(result.keys())}")
        return found

    # Nothing salvageable — report what keys we got to help debug
    top_keys = list(result.keys())
    raise ValueError(
        f"Response missing required fields ('candidates'/'lowongan_id'). "
        f"Got top-level keys: {top_keys}"
    )


def process_streaming_response(response):
    """Process Ollama streaming response and extract JSON result."""
    collected_messages = []
    start_time = datetime.now()
    bar_length = 30
    print("\nProcessing Ollama response...")

    try:
        for line in response.iter_lines():
            if line:
                try:
                    json_response = json.loads(line.decode("utf-8"))
                    if "response" in json_response:
                        collected_messages.append(json_response["response"])
                        elapsed = datetime.now() - start_time
                        filled_length = len(collected_messages) % bar_length
                        bar = "█" * filled_length + "░" * (bar_length - filled_length)
                        print(
                            f"\r[{elapsed.seconds:02d}:{elapsed.microseconds // 10000:02d}] [{bar}]",
                            end="",
                            flush=True,
                        )
                except json.JSONDecodeError:
                    continue

        elapsed_total = datetime.now() - start_time
        print(
            f"\r✓ Completed in {elapsed_total.seconds}.{elapsed_total.microseconds // 10000:02d}s [{'█' * bar_length}]"
        )

        complete_response = "".join(collected_messages)

        # Extract JSON — find outermost { ... }
        start_idx = complete_response.find("{")
        if start_idx == -1:
            raise ValueError("No JSON object found in response")
        end_idx = complete_response.rindex("}") + 1

        json_str = complete_response[start_idx:end_idx]
        result = json.loads(json_str)

        return _validate_and_extract(result)

    except (json.JSONDecodeError, ValueError) as e:
        print(f"\nError parsing response: {str(e)}")
        preview = complete_response[:600] if "complete_response" in dir() else "(no response)"
        if len(complete_response) > 600:
            preview += "..."
        print("Raw response:", preview)
        return None

    except Exception as e:
        print(f"\nError in process_streaming_response: {str(e)}")
        return None
