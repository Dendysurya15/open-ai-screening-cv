import json
import os
from datetime import datetime
import requests

# Path jika dari main.py
from utils.gas_ai import load_prompt_ai, simplify_input_data, save_screening_data

# Path jika langsung ollama_ai.py
# from gas_ai import load_prompt_ai, simplify_input_data, save_screening_data


OLLAMA_CONFIG = {
    "high_quality": {
        "temperature": 0.1,
        "top_p": 0.2,
        "num_predict": 70000,
        "num_ctx": 70000,
        "num_gpu": 24,
        "num_thread": 7
    },
    "fast": {
        "temperature": 0.1,
        "top_p": 0.2,
        "num_predict": 35000,
        "num_ctx": 35000,
        "num_gpu": 12,
        "num_thread": 4
    }
}


def process_streaming_response(response):
    """Process streaming response and combine chunks into complete JSON"""
    collected_messages = []
    start_time = datetime.now()
    print("\nProcessing Ollama response...")
    
    try:
        for line in response.iter_lines():
            if line:
                try:
                    json_response = json.loads(line.decode('utf-8'))
                    if 'response' in json_response:
                        collected_messages.append(json_response['response'])
                        # Calculate elapsed time
                        elapsed = datetime.now() - start_time
                        # Create progress bar
                        bar_length = 30
                        filled_length = len(collected_messages) % bar_length
                        bar = '█' * filled_length + '░' * (bar_length - filled_length)
                        print(f"\r[{elapsed.seconds:02d}:{elapsed.microseconds//10000:02d}] [{bar}]", end="", flush=True)
                except json.JSONDecodeError:
                    continue
        
        # Show completion
        elapsed_total = datetime.now() - start_time
        print(f"\r✓ Processing completed in {elapsed_total.seconds}.{elapsed_total.microseconds//10000:02d}s [{'█' * bar_length}]")
        
        complete_response = ''.join(collected_messages)
        
        try:
            result = json.loads(complete_response)
            if not isinstance(result, dict):
                raise ValueError("Response must be a JSON object")
            if 'candidates' not in result:
                raise ValueError("Response missing 'candidates' field")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            print(f"\nError parsing response: {str(e)}")
            return None
            
    except Exception as e:
        print(f"\nError in process_streaming_response: {str(e)}")
        return None

def evaluate_candidate(input_data, test_mode=False):
    """Evaluate candidate using the Ollama API"""
    try:
        if isinstance(input_data, dict):
            if 'data' in input_data:
                processed_data = input_data['data']
            else:
                processed_data = input_data
        else:
            raise ValueError(f"Invalid input data format. Expected dict, got {type(input_data)}")

        # Get lowongan_id and screening_id
        try:
            if 'lowongan_pekerjaan' in processed_data:
                lowongan_id = processed_data['lowongan_pekerjaan']['id']
                screening_id = processed_data['kandidat'][0]['screning_id']
            elif 'data' in processed_data and 'lowongan_pekerjaan' in processed_data['data']:
                lowongan_id = processed_data['data']['lowongan_pekerjaan']['id']
                screening_id = processed_data['data']['kandidat'][0]['screning_id']
            else:
                raise ValueError("Missing lowongan_id in input data")
        except Exception as e:
            print(f"Error extracting lowongan_id: {str(e)}")
            raise

        try:
            # Get system message and simplified input using gas_ai functions
            system_message = load_prompt_ai(processed_data)
            simplified_input = simplify_input_data(processed_data)
            
            print(f"Sending request to Ollama model with screening_id: {screening_id}")

            # Make request to Ollama API
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3-8b-instruct",
                    "prompt": f"""Kamu adalah {system_message['role_definition']['posisi']} dengan kualifikasi {system_message['role_definition']['kualifikasi']} dan scope kerja {system_message['role_definition']['scope_kerja']} yang bertugas {system_message['role_definition']['task']}. 

Berikan evaluasi dengan format JSON yang TEPAT seperti berikut:
{json.dumps(system_message['output_format'], indent=2, ensure_ascii=False)}

Panduan Penilaian:
{json.dumps(system_message['scoring_rules'], indent=2, ensure_ascii=False)}

Panduan Evaluasi:
{json.dumps(system_message['evaluation_steps'], indent=2, ensure_ascii=False)}

Rekomendasi Rules:
{json.dumps(system_message['rekomendasi_rules'], indent=2, ensure_ascii=False)}

Strict Rules:
{json.dumps(system_message['strict_rules'], indent=2, ensure_ascii=False)}

Validation Rules:
{json.dumps(system_message['validation_rules'], indent=2, ensure_ascii=False)}

Untuk pertanyaan_skrining jika ada kategori pernyataan dan jawaban pernyataan dari kandidat adalah 1 berarti Ya dan 0 berarti tidak.

Input data untuk dievaluasi:
{json.dumps(simplified_input, indent=2, ensure_ascii=False)}


PENTING: Response HARUS dalam format JSON yang valid dan TEPAT sesuai format di atas.
""",
                    "stream": True,
                    "options": OLLAMA_CONFIG["high_quality"]
                },
                stream=True,
                timeout=300
            )

            # Check response status
            if response.status_code != 200:
                print(f"\nError: Ollama API returned status code {response.status_code}")
                print(f"Response content: {response.text}")
                raise Exception(f"Ollama API error: {response.status_code}")

            # Process response
            result = process_streaming_response(response)

            if result and isinstance(result, dict):
                if 'lowongan_id' not in result:
                    result['lowongan_id'] = lowongan_id
                
                save_screening_data(simplified_input, result, screening_id, test_mode)
                return result
            else:
                raise ValueError(f"Invalid response format from AI. Got: {type(result)}")

        except requests.exceptions.RequestException as e:
            print(f"\nError connecting to Ollama API: {str(e)}")
            print("Please check if Ollama is running and accessible at http://localhost:11434")
            raise
            
        except Exception as e:
            print(f"\nError in API call or response processing: {str(e)}")
            raise

    except Exception as e:
        print(f"Evaluation failed with error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
        return None

def main():
    """Command line interface for direct JSON processing"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Process candidate evaluation using Ollama AI')
    parser.add_argument('--i', '--input', help='Input JSON file path', required=True)
    parser.add_argument('--o', '--output', help='Output JSON file path', required=True)
    
    args = parser.parse_args()
    
    try:
        # Read input JSON
        with open(args.i, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        # Process the data with test_mode=True for testing
        result = evaluate_candidate(input_data, test_mode=True)
        
        if result:
            # Write output JSON
            with open(args.o, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Successfully processed and saved results to {args.o}")
            print(f"Using Ollama model: llama3-8b-instruct")
        else:
            print("Processing failed - no result generated")
            sys.exit(1)
            
    except FileNotFoundError:
        print(f"Error: Could not find input file {args.i}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in input file {args.i}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

# Tambahkan fungsi generate_prompt yang dibutuhkan main.py
def generate_prompt(lowongan_id, data, is_simplified=True):
    """Generate prompt for AI evaluation"""
    system_message = load_prompt_ai(data)
    if is_simplified:
        data = simplify_input_data(data)
    
    return {
        "model": "llama3-8b-instruct",
        "prompt": f"""Kamu adalah {system_message['role']}. {system_message['task']}.

Berikan evaluasi dengan format JSON yang TEPAT seperti berikut:
{json.dumps(system_message['output_format'], indent=2, ensure_ascii=False)}

Panduan Penilaian:
{json.dumps(system_message['scoring_rules'], indent=2, ensure_ascii=False)}

Rekomendasi Rules:
{json.dumps(system_message['rekomendasi_rules'], indent=2, ensure_ascii=False)}

Input data untuk dievaluasi:
{json.dumps(data, indent=2, ensure_ascii=False)}

PENTING: Response HARUS dalam format JSON yang valid dan TEPAT sesuai format di atas.
"""
    }
