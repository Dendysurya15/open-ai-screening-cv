import openai
import json
import argparse

def process_streaming_response(stream):
    """
    Process streaming response and combine chunks into complete JSON
    """
    collected_messages = []
    
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            collected_messages.append(chunk.choices[0].delta.content)
    
    complete_response = ''.join(collected_messages)
    
    # Try to parse the complete response as JSON
    try:
        return json.loads(complete_response)
    except json.JSONDecodeError:
        print("Warning: Could not parse response as JSON")
        return complete_response

def evaluate_candidate(input_data):
    """
    Evaluate candidate using the OpenAI API
    """
    try:
        # # Initialize OpenAI client
        client = openai.OpenAI(
            base_url="http://localhost:1234/v1", 
            api_key="lm-studio"
        )
        
                # Initialize OpenAI client
        # client = openai.OpenAI(
        #     base_url="http://10.9.116.175:1234/v1", 
        #     api_key="lm-studio"
        # )


        # Create chat completion with streaming
        stream = client.chat.completions.create(
            model="meta-llama-3.1-8b-instruct",
            #Meta-Llama-3.1-8B-Instruct-Q6_K_L.gguf
            messages=[
                {
                    "role": "system",
                    "content": """Anda adalah rekruter HR profesional di PT CBI (perusahaan Perkebunan dan Pengolahan Kelapa Sawit) Pangkalan Bun - Kalimantan Tengah yang melakukan evaluasi kandidat secara mendalam dalam format JSON.

Untuk setiap kandidat, buat penilaian terperinci dengan fokus pada:
1. Memberikan penilaian menyeluruh untuk setiap kategori evaluasi utama
2. Menghasilkan analisis deskriptif yang mendalam
Format JSON untuk input akan diberikan user
Format output hanya JSON saja
  "candidates": [
    {
      "id_kandidat": id,
      "nama_lengkap": "name",
    "penilaian": [
                {
                    "kategori": "pendidikan",
                    "nilai": "1-5",
                    "uraian": "Penilaian komprehensif latar belakang pendidikan"
                },
                {
                    "kategori": "pengalaman",
                    "nilai": "1-5",
                    "uraian": "Penilaian komprehensif pengalaman dan riwayat pekerjaan"
                },         
                {  
                    "kategori": "sertifikat_keahlian",
                    "nilai": "1-5",
                    "uraian": "Penilaian komprehensif pertanyaan skrining untuk sertifikat_keahlian"
                },
                {
                    "kategori": "keterampilan",
                    "nilai": "1-5",
                    "uraian": "Penilaian komprehensif pertanyaan skrining untuk kategori keterampilan teknis dan non teknis"
                },
                {
                    "kategori": "jawaban_pertanyaan_skrining_operasional_kebun",
                    "nilai": "1-5",
                    "uraian": "Penilaian komprehensif pertanyaan skrining untuk kategori operasional_kebun"
                },
                {
                    "kategori": "jawaban_pertanyaan_skrining_general",
                    "nilai": "1-5",
                    "uraian": "Penilaian komprehensif pertanyaan skrining untuk kategori general"
                },
                {
                    "kategori": "jawaban_pertanyaan_skrining_pernyataan",
                    "nilai": "1-5",
                    "uraian": "Penilaian komprehensif pertanyaan skrining untuk kategori pernyataan"
                }
            ]
            }
            ],"""
                },
                {
                    "role": "user",
                    "content": json.dumps(input_data, indent=2)
                }
            ],
            temperature=0.1,
            max_completion_tokens=-1,
            stream=True
        )

        # Process the streaming response
        result = process_streaming_response(stream)
        return result

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return None

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Evaluate candidates from JSON input file')
    parser.add_argument('--input_file', '-i', help='Path to input JSON file')
    parser.add_argument('--output', '-o', help='Path to output JSON file (optional)')
    args = parser.parse_args()

    # Read input data
    try:
        with open(args.input_file, 'r') as file:
            input_data = json.load(file)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found")
        return
    except json.JSONDecodeError:
        print(f"Error: '{args.input_file}' is not a valid JSON file")
        return

    # Evaluate candidate
    result = evaluate_candidate(input_data)
    
    if result:
        # If output file is specified, write to file
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as file:
                    json.dump(result, file, indent=2, ensure_ascii=False)
                print(f"Results written to {args.output}")
            except Exception as e:
                print(f"Error writing to output file: {str(e)}")
        # Otherwise print to console
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()