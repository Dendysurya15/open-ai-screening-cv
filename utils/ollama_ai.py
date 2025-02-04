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
        
        # Join all collected messages
        complete_response = ''.join(collected_messages)
        
        # Try to find the JSON object in the response
        try:
            # Look for the first { and last } to extract the JSON object
            start_idx = complete_response.find('{')
            end_idx = complete_response.rindex('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = complete_response[start_idx:end_idx]
                result = json.loads(json_str)
                
                # Validate the structure
                if not isinstance(result, dict):
                    raise ValueError("Response must be a JSON object")
                if 'candidates' not in result:
                    # Try to fix common formatting issues
                    if 'lowongan_id' in result:
                        return result  # Already in correct format
                    else:
                        raise ValueError("Response missing required fields")
                return result
            else:
                raise ValueError("Could not find valid JSON object in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            print(f"\nError parsing response: {str(e)}")
            print("Raw response:", complete_response[:500] + "..." if len(complete_response) > 500 else complete_response)
            return None
            
    except Exception as e:
        print(f"\nError in process_streaming_response: {str(e)}")
        return None

def get_prompt_ai():
    # url = "http://localhost:8000/api/prompt-ai"
    url = "https://recruitment-ai.cbicareer.com/api/prompt-ai"
    token = os.getenv('SACTUM_API_KEY') 
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }

    # print(f"Getting prompt AI from {url}")
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print(f"Prompt AI received from {url}")

            return response.json()
        else:
            print(f"Error getting prompt AI: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error getting prompt AI: {str(e)}")

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

            # model ai by server
            prompts = get_prompt_ai()
            modal_version = prompts['data']['version']
            print(f"Model AI version: {modal_version}")
            system_message = prompts['data']['promptModel']['default_system_message']
            # model ai by local
            # current_dir = os.path.dirname(os.path.abspath(__file__))
            # prompt_path = os.path.join(current_dir, 'prompt_ai.json')
            # with open(prompt_path, 'r') as file:
            #     prompts = json.load(file)
            # system_message = prompts['default_system_message']
            simplified_input = simplify_input_data(processed_data)
    


            print(f"Sending request to Ollama model with screening_id: {screening_id}")

            # Make request to Ollama API
            response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3-8b-instruct",
                "prompt": f"""Kamu adalah {system_message['peran']['posisi']} dengan kualifikasi {system_message['peran']['kualifikasi']}, cakupan {system_message['peran']['cakupan']}, dan bertugas {system_message['peran']['tugas']}.
            Instruksi:
            1. Jawab dalam bahasa Indonesia.
            2. Evaluasi kandidat sesuai panduan dan format output berikut:
            - Hanya nilai kategori yang tercantum di key_pertanyaan_screening.
            - Format kategori: "jawaban_pertanyaan_skrining_[nama_kategori]".
            - Contoh: Jika key_pertanyaan_screening="supporting,general,pernyataan", maka hanya nilai kategori tersebut.
            3. Abaikan tag HTML (misal: <p>, <strong>, dll.) dalam teks evaluasi.
            4. Untuk kategori "pernyataan":
            - Jawaban "1" berarti setuju dan "0" berarti tidak setuju, namun jangan gunakan nilai mentah tersebut sebagai skor evaluasi.
            - Berikan nilai evaluasi dalam skala 1-5 berdasarkan kesesuaian jawaban dengan requirement posisi.
            - Contoh: Jika requirement mengharuskan kesediaan tinggi dan kandidat menjawab "1", berikan skor evaluasi 4 atau 5; jika kandidat menjawab "0", berikan skor rendah (misalnya 1 atau 2).
            5. Response HARUS berupa JSON valid sesuai format di bawah, tanpa teks tambahan:
            {json.dumps(system_message['output_format'], indent=2, ensure_ascii=False)}

            Panduan Penilaian:
            {json.dumps(system_message['evaluasi'], indent=2, ensure_ascii=False)}

            PERINGATAN: Jika ada kategori yang tidak ada di key_pertanyaan_screening, evaluasi dianggap GAGAL.

            Input data:
            {json.dumps(simplified_input, indent=2, ensure_ascii=False)}
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
