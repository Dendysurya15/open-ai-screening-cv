import json
import time
import requests
from config.settings import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_CONFIG, TIMEOUT_CONFIG
from services.api_client import get_prompt_ai
from utils.data_processor import simplify_input_data, save_screening_data
from utils.response_parser import process_streaming_response


def check_ollama_health():
    """Check if Ollama service is running and responsive."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def make_ollama_request(prompt, max_retries=None):
    """Make request to Ollama API with retry logic and adaptive timeout."""
    if max_retries is None:
        max_retries = TIMEOUT_CONFIG["retry_attempts"]

    if not check_ollama_health():
        raise Exception(
            f"Ollama service is not running or not accessible at {OLLAMA_URL}"
        )

    timeout = TIMEOUT_CONFIG["initial_timeout"]

    for attempt in range(max_retries):
        try:
            # Select quality tier based on attempt number
            if attempt == 0:
                options = OLLAMA_CONFIG["high_quality"]
            elif attempt == 1:
                options = OLLAMA_CONFIG["fast"]
            else:
                options = OLLAMA_CONFIG["conservative"]

            print(f"Attempt {attempt + 1}/{max_retries} - Timeout: {timeout}s")

            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": True,
                    "options": options,
                },
                stream=True,
                timeout=timeout,
            )

            if response.status_code == 200:
                return response

            print(
                f"Ollama API returned status code {response.status_code}: {response.text}"
            )

            if (
                response.status_code == 500
                and "llama runner process has terminated" in response.text
            ):
                print("❌ Ollama runner crashed - insufficient memory or GPU issues")
                if attempt < max_retries - 1:
                    wait_time = (TIMEOUT_CONFIG["backoff_factor"] ** attempt) * 60
                    print(f"⏳ Waiting {wait_time}s for recovery...")
                    time.sleep(wait_time)
                else:
                    raise Exception("Ollama runner keeps crashing. Check resources.")

            elif response.status_code == 400:
                raise Exception(f"Bad request: {response.text}")

            else:
                if attempt < max_retries - 1:
                    wait_time = (TIMEOUT_CONFIG["backoff_factor"] ** attempt) * 30
                    print(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise Exception(
                        f"Ollama API error: {response.status_code} - {response.text}"
                    )

        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt + 1} (timeout: {timeout}s)")
            if attempt < max_retries - 1:
                timeout = min(timeout * 2, TIMEOUT_CONFIG["max_timeout"])
                wait_time = (TIMEOUT_CONFIG["backoff_factor"] ** attempt) * 30
                print(f"Retrying with timeout {timeout}s in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise

        except requests.exceptions.ConnectionError as e:
            print(f"Connection error on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = (TIMEOUT_CONFIG["backoff_factor"] ** attempt) * 30
                print(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception(f"Failed to connect after {max_retries} attempts")

    raise Exception(f"Failed to get response after {max_retries} attempts")


def build_prompt(system_message, simplified_input):
    """Build the evaluation prompt from system message and input data."""
    output_format_str = json.dumps(system_message['output_format'], indent=2, ensure_ascii=False)
    aturan = system_message.get('aturan_wajib', [])
    aturan_wajib_str = (
        "\nATURAN WAJIB (utama, kalahkan instruksi lain bila bentrok):\n"
        + "\n".join(f"- {a}" for a in aturan)
    ) if aturan else ""
    return f"""Kamu adalah {system_message['peran']['posisi']} dengan kualifikasi {system_message['peran']['kualifikasi']}, cakupan {system_message['peran']['cakupan']}, dan bertugas {system_message['peran']['tugas']}.

Panduan Penilaian:
{json.dumps(system_message['evaluasi'], indent=2, ensure_ascii=False)}

Instruksi:
1. Jawab dalam bahasa Indonesia.
2. Evaluasi kandidat sesuai panduan penilaian di atas.
3. Kategori INTI (pendidikan, pengalaman, sertifikat_keahlian, keterampilan) WAJIB selalu dinilai 1-5.
   - DILARANG memberi nilai 0 pada kategori inti.
   - Jika data kategori inti tidak ada (mis. sertifikat null), beri nilai 1 dan jelaskan di uraian bahwa datanya tidak tersedia.
   - uraian kategori inti WAJIB diisi alasan konkret merujuk data. DILARANG kosong.
4. Kategori skrining ("jawaban_pertanyaan_skrining_[nama]"): hanya yang tercantum di key_pertanyaan_screening yang dinilai 1-5.
   - Yang TIDAK tercantum di key_pertanyaan_screening: beri nilai "0".
5. Abaikan tag HTML (misal: <p>, <strong>, dll.) dalam teks evaluasi.
6. Untuk kategori "pernyataan":
   - Jawaban "1" berarti setuju dan "0" berarti tidak setuju.
   - Berikan nilai evaluasi dalam skala 1-5 berdasarkan kesesuaian dengan requirement posisi.
{aturan_wajib_str}

Input data:
{json.dumps(simplified_input, indent=2, ensure_ascii=False)}

FORMAT OUTPUT — WAJIB DIIKUTI PERSIS:
Output kamu HARUS berupa JSON valid dengan struktur PERSIS seperti berikut:

{output_format_str}

PERINGATAN KRITIS:
- Output HANYA JSON di atas. Mulai dengan karakter `{{` dan akhiri dengan `}}`.
- DILARANG menambahkan key tambahan seperti "response_type", "encoding", "root_fields", "scoring", atau key apapun yang tidak ada di format di atas.
- DILARANG menambahkan teks apapun sebelum atau sesudah JSON (tidak ada penjelasan, tidak ada markdown ```json).
- Semua nilai "nilai" HARUS berupa string angka. Kategori inti 1-5 (jangan 0). Kategori skrining 0 hanya jika tak ada di key_pertanyaan_screening.
- DILARANG nilai kosong, tanda "-", atau uraian kosong pada kategori inti.
"""


def evaluate_candidate(input_data, test_mode=False):
    """Evaluate a candidate using the Ollama AI model.

    Returns the evaluation result dict or None on failure.
    """
    try:
        # Extract processed data
        if isinstance(input_data, dict):
            processed_data = input_data.get("data", input_data)
        else:
            raise ValueError(
                f"Invalid input data format. Expected dict, got {type(input_data)}"
            )

        # Get lowongan_id and screening_id
        if "lowongan_pekerjaan" in processed_data:
            lowongan_id = processed_data["lowongan_pekerjaan"]["id"]
            screening_id = processed_data["kandidat"][0]["screning_id"]
        elif "data" in processed_data and "lowongan_pekerjaan" in processed_data["data"]:
            lowongan_id = processed_data["data"]["lowongan_pekerjaan"]["id"]
            screening_id = processed_data["data"]["kandidat"][0]["screning_id"]
        else:
            raise ValueError("Missing lowongan_pekerjaan in input data")

        # Get prompt (server or local fallback)
        system_message = get_prompt_ai()

        # Simplify input for token efficiency
        simplified_input = simplify_input_data(processed_data)

        print(f"Sending request to Ollama model with screening_id: {screening_id}")

        # Build and send prompt
        prompt_text = build_prompt(system_message, simplified_input)
        response = make_ollama_request(prompt_text)

        if response.status_code != 200:
            raise Exception(f"Ollama API error: {response.status_code}")

        # Parse response
        result = process_streaming_response(response)

        if result and isinstance(result, dict):
            if "lowongan_id" not in result:
                result["lowongan_id"] = lowongan_id
            save_screening_data(simplified_input, result, screening_id, test_mode)
            return result
        else:
            raise ValueError(f"Invalid response format from AI. Got: {type(result)}")

    except Exception as e:
        print(f"Evaluation failed: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None
