import openai
import json

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
        # Initialize OpenAI client
        client = openai.OpenAI(
            base_url="http://localhost:1234/v1", 
            api_key="lm-studio"
        )

        # Create chat completion with streaming
        stream = client.chat.completions.create(
            model="QuantFactory/Meta-Llama-3.1-8B-Instruct-GGUF",
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
                    "kategori": "Pendidikan",
                    "nilai": "1-5",
                    "uraian": "Penilaian komprehensif latar belakang pendidikan"
                },
                {
                    "kategori": "Riwayat Pekerjaan",
                    "nilai": "1-5",
                    "uraian": "Penilaian komprehensif pengalaman kerja"
                },
                
                        {  
                            "kategori": "general",
                            "nilai": "1-5",
                            "uraian": "Penilaian komprehensif pertanyaan skrining untuk kategori general"
                        },
                        {
                            "kategori": "pernyataan",
                            "nilai": "1-5",
                            "uraian": "Penilaian komprehensif pertanyaan skrining untuk kategori pernyataan"
                        },
                        {
                            "kategori": "operasional",
                            "nilai": "1-5",
                            "uraian": "Penilaian komprehensif pertanyaan skrining untuk kategori operasional_kebun"
        
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

# Read input data
with open('input.json', 'r') as file:
    input_data = json.load(file)

# Evaluate candidate and print result
result = evaluate_candidate(input_data)
if result:
    print(json.dumps(result, indent=2, ensure_ascii=False))