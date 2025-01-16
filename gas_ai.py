import openai
import json
from datetime import datetime

def process_streaming_response(stream):
    """Process streaming response and combine chunks into complete JSON"""
    collected_messages = []
    
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            collected_messages.append(chunk.choices[0].delta.content)
    
    complete_response = ''.join(collected_messages)
    
    try:
        return json.loads(complete_response)
    except json.JSONDecodeError:
        print("Warning: Could not parse response as JSON")
        return complete_response

def load_prompt_ai():
    with open('prompt_ai.json', 'r') as file:
        return json.load(file)

def simplify_input_data(input_data):
    """Create simplified version of input data"""
    return {
        "lowongan_pekerjaan": input_data["lowongan_pekerjaan"],
        "kandidat": [{
            "id": input_data["kandidat"][0]["id"],
            "nama_lengkap": input_data["kandidat"][0]["nama_lengkap"],
            "pendidikan": {
                "formal": input_data["kandidat"][0]["pendidikan"]["formal"][-2:],
                "non_formal": input_data["kandidat"][0]["pendidikan"].get("non_formal", [])[:2]
            },
            "pengalaman": {
                "pengalaman_pekerjaan": input_data["kandidat"][0]["pengalaman"]["pengalaman_pekerjaan"][:2], 
                "tanggung_jawab_pada_pekerjaan_terakhir": input_data["kandidat"][0]["pengalaman"]["tanggung_jawab_pada_pekerjaan_terakhir"]
            },
            "jawaban_pertanyaan_skrining": input_data["kandidat"][0]["jawaban_pertanyaan_skrining"]
        }]
    }

def evaluate_candidate(input_data):
    """Evaluate candidate using the OpenAI API"""
    
    # Load system message from prompt_ai.json
    prompts = load_prompt_ai()
    
    try:
        # Extract lowongan_id from input data
        lowongan_id = input_data['lowongan_pekerjaan']['id']
        
        client = openai.OpenAI(
            base_url="http://10.9.116.125:1234/v1", 
            api_key="lm-studio"
        )

        # Try with full input data first
        try:
            stream = client.chat.completions.create(
                model="meta-llama-3.1-8b-instruct",
                messages=[
                    {"role": "system", "content": json.dumps(prompts['default_system_message'], ensure_ascii=False)},
                    {"role": "user", "content": f"Evaluasi kandidat berikut untuk lowongan dengan ID {lowongan_id}:\n" + json.dumps(input_data, indent=2, ensure_ascii=False)}
                ],
                temperature=0.2,
                max_completion_tokens=-1,
                stream=True
            )
            result = process_streaming_response(stream)
            
        except Exception as e:
            print("Trying with simplified input due to:", str(e))
            # If failed, try with simplified input
            simplified_input = simplify_input_data(input_data)
            stream = client.chat.completions.create(
                model="meta-llama-3.1-8b-instruct",
                messages=[
                    {"role": "system", "content": json.dumps(prompts['default_system_message'], ensure_ascii=False)},
                    {"role": "user", "content": f"Evaluasi kandidat berikut untuk lowongan dengan ID {lowongan_id}:\n" + json.dumps(simplified_input, indent=2, ensure_ascii=False)}
                ],
                temperature=0.2,
                stream=True
            )
            result = process_streaming_response(stream)

        # Ensure lowongan_id is in the result
        if result and isinstance(result, dict) and 'lowongan_id' not in result:
            result['lowongan_id'] = lowongan_id
            
        return result

    except Exception as e:
        print("Both attempts failed:")
        print(f"Error in evaluate_candidate: {str(e)}")
        return None
