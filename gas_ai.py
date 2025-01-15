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

def evaluate_candidate(input_data):
    """Evaluate candidate using the OpenAI API"""
    try:
        # Extract lowongan_id from input data
        lowongan_id = input_data['lowongan_pekerjaan']['id']
        
        client = openai.OpenAI(
            base_url="http://10.9.116.125:1234/v1", 
            api_key="lm-studio"
        )

        # Create chat completion with streaming
        stream = client.chat.completions.create(
            model="meta-llama-3.1-8b-instruct",
            messages=[
                {
                    "role": "system",
                    "content": """Anda adalah rekruter HR profesional di PT CBI (perusahaan Perkebunan dan Pengolahan Kelapa Sawit) Pangkalan Bun - Kalimantan Tengah yang melakukan evaluasi kandidat secara mendalam dalam format JSON.

Untuk setiap kandidat, buat penilaian terperinci dengan fokus pada:
1. Memberikan penilaian menyeluruh untuk setiap kategori evaluasi utama
2. Menghasilkan analisis deskriptif yang mendalam
3. Pastikan untuk menyertakan lowongan_id dari data input

Format output JSON:
{
  "lowongan_id": id_lowongan,
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
          "uraian": "Penilaian komprehensif sertifikat keahlian"
        },
        {
          "kategori": "keterampilan",
          "nilai": "1-5",
          "uraian": "Penilaian komprehensif keterampilan teknis dan non teknis"
        },
        {
          "kategori": "jawaban_pertanyaan_skrining_operasional_kebun",
          "nilai": "1-5",
          "uraian": "Penilaian komprehensif pertanyaan operasional kebun"
        },
        {
          "kategori": "jawaban_pertanyaan_skrining_general",
          "nilai": "1-5",
          "uraian": "Penilaian komprehensif pertanyaan general"
        },
        {
          "kategori": "jawaban_pertanyaan_skrining_pernyataan",
          "nilai": "1-5",
          "uraian": "Penilaian komprehensif pertanyaan pernyataan"
        }
      ],
      "rekomendasi": "Disarankan/Tidak disarankan",
      "ringkasan_penilaian": "Ringkasan singkat evaluasi keseluruhan kandidat"
    }
  ]
}"""
                },
                {
                    "role": "user",
                    "content": f"Evaluasi kandidat berikut untuk lowongan dengan ID {lowongan_id}:\n" + json.dumps(input_data, indent=2)
                }
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
        print(f"Error in evaluate_candidate: {str(e)}")
        return None

def process_mysql_screening(screening_data):
    
    """Process a single screening from MySQL data"""
    try:
        # Parse the JSON data from MySQL
        if isinstance(screening_data, str):
            data = json.loads(screening_data)
        else:
            data = screening_data

        # Extract the relevant data for evaluation
        if 'data' in data:
            result = evaluate_candidate(data['data'])
            
            if result:
                # Generate timestamp for the output file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screening_id = data['data']['kandidat'][0]['screning_id']
                output_filename = f"output_{screening_id}_{timestamp}.json"
                
                # Save the result to a JSON file
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                
                return True, output_filename
            
        return False, None

    except Exception as e:
        print(f"Error in process_mysql_screening: {str(e)}")
        return False, None