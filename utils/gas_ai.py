import openai
import json
import os
from datetime import datetime

def process_streaming_response(stream):
    """Process streaming response and combine chunks into complete JSON"""
    collected_messages = []
    
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            collected_messages.append(chunk.choices[0].delta.content)
    
    complete_response = ''.join(collected_messages)
    
    try:
        result = json.loads(complete_response)
        # Add validation for required fields
        if not isinstance(result, dict):
            raise ValueError("Response must be a JSON object")
        if 'candidates' not in result:
            raise ValueError("Response missing 'candidates' field")
        return result
    except json.JSONDecodeError:
        print("Warning: Could not parse response as JSON")
        return None  # Return None instead of unparsed response

def load_prompt_ai(input_data):
    """Load and configure AI prompt based on input data"""
    # Get the directory where the current script (gas_ai.py) is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, 'prompt_ai.json')
    
    with open(prompt_path, 'r') as file:
        prompts = json.load(file)
    
    # Define base penilaian categories
    penilaian_candidate = [
        {
            "kategori": "pendidikan",
            "nilai": "1-5", 
            "uraian": "Penilaian komprehensif latar belakang pendidikan mencakup:\n- Kesesuaian jurusan dengan posisi\n- Level pendidikan\n- Prestasi akademik\n- Akreditasi institusi"
        },
        {
            "kategori": "pengalaman",
            "nilai": "1-5",
            "uraian": "Penilaian komprehensif pengalaman kerja mencakup:\n- Relevansi pengalaman dengan posisi\n- Durasi pengalaman\n- Progress karir\n- Pencapaian dan kontribusi\n- Stabilitas kerja"
        },
        {
            "kategori": "sertifikat_keahlian", 
            "nilai": "1-5",
            "uraian": "Penilaian komprehensif sertifikasi mencakup:\n- Relevansi dengan posisi\n- Level sertifikasi\n- Reputasi lembaga sertifikasi\n- Masa berlaku sertifikat"
        },
        {
            "kategori": "keterampilan",
            "nilai": "1-5",
            "uraian": "Penilaian komprehensif keterampilan mencakup:\n- Hard skills sesuai requirement\n- Soft skills (komunikasi, leadership, dll)\n- Tools & teknologi yang dikuasai\n- Bahasa yang dikuasai"
        }
    ]
    
    screening_categories = input_data.get('key_pertanyaan_screening', '').split(',')
    
    # Add dynamic screening categories
    for category in screening_categories:
        # Remove any whitespace and convert to snake_case
        category_clean = category.strip()
        category_snake = category_clean.lower().replace(' ', '_')
        
        penilaian_candidate.append({
            "kategori": f"jawaban_pertanyaan_skrining_{category_snake}",
            "nilai": "1-5",
            "uraian": f"Penilaian komprehensif pertanyaan skrining untuk {category_clean} mencakup:\n"
                      f"- Ketepatan dan relevansi jawaban\n"
                      f"- Kedalaman pemahaman terhadap topik\n"
                      f"- Kemampuan menjelaskan dengan terstruktur\n"
                      f"- Pengalaman praktis terkait topik\n"
                      f"- Kesesuaian dengan kebutuhan posisi"
        })
    
    # Add penilaian_candidate to system message
    prompts['default_system_message']['output_format']['candidates'][0]['penilaian'] = penilaian_candidate
    
    return prompts['default_system_message']

def simplify_input_data(input_data):
    """Modify function to handle different formal education structures"""
    kandidat = input_data["kandidat"][0]
    pengalaman = kandidat.get("pengalaman", {})
    
    # Limit non-formal education entries
    pendidikan = kandidat.get("pendidikan", {})
    if pendidikan and pendidikan.get("non_formal"):
        pendidikan["non_formal"] = pendidikan["non_formal"][:3]  # Take only first 3 entries
        
    # Simplify work experience descriptions
    work_experience = pengalaman.get("pengalaman_pekerjaan", [])
    if work_experience:
        for exp in work_experience:
            # Limit jobdesk length
            if "jobdesk" in exp:
                exp["jobdesk"] = "\n".join(exp["jobdesk"].split("\n")[:3])  # Take only first 3 lines
        work_experience = work_experience[:2]  # Take only first 2 entries
    
    return {
        "lowongan_pekerjaan": input_data["lowongan_pekerjaan"],
        "key_pertanyaan_screening": input_data.get("key_pertanyaan_screening", ""),
        "kandidat": [{
            "id": kandidat["id"],
            "nama_lengkap": kandidat["nama_lengkap"],
            "pendidikan": pendidikan,
            "pengalaman": {
                "pengalaman_pekerjaan": work_experience,
                "tanggung_jawab_pada_pekerjaan_terakhir": pengalaman.get("tanggung_jawab_pada_pekerjaan_terakhir", "")[:200]  # Limit length
            },
            "jawaban_pertanyaan_skrining": kandidat.get("jawaban_pertanyaan_skrining", {})
        }]
    }

def save_screening_data(input_data, result, screening_id, test_mode=False):
    """Save screening input and result data to JSON files"""
    if not test_mode:
        return
        
    try:
        # Create screening_ai directory if it doesn't exist
        screening_dir = "screening_ai"
        if not os.path.exists(screening_dir):
            os.makedirs(screening_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save input data
        input_filename = f"input_screening_{screening_id}_{timestamp}.json"
        input_filepath = os.path.join(screening_dir, input_filename)
        with open(input_filepath, 'w', encoding='utf-8') as f:
            json.dump(input_data, f, indent=2, ensure_ascii=False)
            
        # Save result data
        result_filename = f"result_screening_{screening_id}_{timestamp}.json"
        result_filepath = os.path.join(screening_dir, result_filename)
        with open(result_filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            
        print(f"\nTest Mode - Saved screening data:")
        print(f"Input: {input_filepath}")
        print(f"Result: {result_filepath}")
        
    except Exception as e:
        print(f"Error saving screening test data: {str(e)}")

def evaluate_candidate(input_data, test_mode=False):
    """Evaluate candidate using the OpenAI API"""
    try:
        # Handle both direct JSON and database format
        if isinstance(input_data, dict):
            # print("Input data is a dictionary")
            if 'data' in input_data:
                # Database format - data is nested
                processed_data = input_data['data']
                # print("Using nested data format")
            else:
                # Direct JSON format - data is at root level
                processed_data = input_data
                # print("Using root level data format")
        else:
            raise ValueError(f"Invalid input data format. Expected dict, got {type(input_data)}")

        # Get lowongan_id and screening_id - handle both formats
        try:
            if 'lowongan_pekerjaan' in processed_data:
                lowongan_id = processed_data['lowongan_pekerjaan']['id']
                screening_id = processed_data['kandidat'][0]['screning_id']
            elif 'data' in processed_data and 'lowongan_pekerjaan' in processed_data['data']:
                lowongan_id = processed_data['data']['lowongan_pekerjaan']['id']
                screening_id = processed_data['data']['kandidat'][0]['screning_id']
            else:
                raise ValueError("Missing lowongan_id in input data")
            # print(f"Found lowongan_id: {lowongan_id}")
           
        except Exception as e:
            print(f"Error extracting lowongan_id: {str(e)}")
            raise

        # Get system message with all prompts configured based on input data
        try:
            system_message = load_prompt_ai(processed_data)
            # print("Successfully loaded system message")
        except Exception as e:
            print(f"Error loading prompt_ai: {str(e)}")
            raise

        try:
            client = openai.OpenAI(
                base_url="http://10.9.116.125:54696/v1", 
                api_key="lm-studio"
            )
            print("OpenAI client initialized")

            # Use simplified input by default
            simplified_input = simplify_input_data(processed_data)
            # print("Input data simplified successfully")
            # print(f"Found screening_id: {screening_id}")
            print(f"Sending request to AI model with screening_id: {screening_id}")
            stream = client.chat.completions.create(
                model="meta-llama-3.1-8b-instruct",
                messages=[
                    {"role": "system", "content": json.dumps(system_message, ensure_ascii=False)},
                    {"role": "user", "content": f"Evaluasi kandidat berikut untuk lowongan dengan ID {lowongan_id}:\n" + json.dumps(simplified_input, indent=2, ensure_ascii=False)}
                ],
                temperature=0.1,
                stream=True,
                timeout = 600
            )
            # print("Request sent, processing response...")
            result = process_streaming_response(stream)
            # print("Response processed")

            # Ensure lowongan_id is in the result
            if result and isinstance(result, dict):
                if 'lowongan_id' not in result:
                    result['lowongan_id'] = lowongan_id
                    
                # Save test data if test_mode is enabled
                save_screening_data(simplified_input, result, screening_id, test_mode)
                    
                return result
            else:
                raise ValueError(f"Invalid response format from AI. Got: {type(result)}")

        except Exception as e:
            print(f"Error in API call or response processing: {str(e)}")
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
    
    parser = argparse.ArgumentParser(description='Process candidate evaluation using AI')
    parser.add_argument('--i', '--input', help='Input JSON file path', required=True)
    parser.add_argument('--o', '--output', help='Output JSON file path', required=True)
    
    args = parser.parse_args()
    
    try:
        # Read input JSON
        with open(args.i, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        # Process the data
        result = evaluate_candidate(input_data)
        
        if result:
            # Write output JSON
            with open(args.o, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Successfully processed and saved results to {args.o}")
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
