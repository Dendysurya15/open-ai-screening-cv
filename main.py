import os
import sys
import json
from dotenv import load_dotenv
import schedule
import time
from threading import Thread
from pysher import Pusher as PysherClient
# import utils.gas_ai as gas_ai
import utils.ollama_ai as gas_ai
from datetime import datetime
from utils.send_data import process_completed_screenings
from utils.database import connect_to_mysql 
import requests
# from process_result_ai import process_result_ai
# Load environment variables
load_dotenv()

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now we can import from utils
import utils.ollama_ai as gas_ai
from utils.send_data import process_completed_screenings
from utils.database import connect_to_mysql 

def check_screening_exists(cursor, screening_id):
    query = "SELECT COUNT(*) FROM cronjob WHERE screening_id = %s"
    cursor.execute(query, (screening_id,))
    count = cursor.fetchone()[0]
    return count > 0

def insert_to_cronjob(data):
    try:
        # Parse JSON if string
        if isinstance(data, str):
            data = json.loads(data)
        
        # Handle data from pusher (single data)
        if 'status' not in data:
            processed_data = {
                'status': True,
                'message': 'Success',
                'data': data['data']
            }
            data_list = [processed_data]
        else:
            # Handle data from API (could be single or bulk)
            if isinstance(data.get('data'), list):
                data_list = [{'status': data['status'], 'message': data['message'], 'data': item} for item in data['data']]
            else:
                data_list = [data]

        conn = connect_to_mysql()
        cursor = conn.cursor()
        
        inserted_screening_ids = []  # Track newly inserted screenings
        
        for processed_data in data_list:
            # Skip if no data
            if not processed_data.get('data'):
                print("Tidak ada data untuk diproses")
                continue
                
            # Get kandidat list
            kandidat_list = processed_data['data'].get('kandidat', [])
            if not kandidat_list:
                print("Tidak ada data kandidat yang tersedia")
                continue
            
            # Insert each kandidat
            for kandidat in kandidat_list:
                screening_id = kandidat['screning_id']
                
                # Check if screening_id exists
                if check_screening_exists(cursor, screening_id):
                    print(f"Data dengan screening_id {screening_id} sudah ada dalam database!")
                    continue
                
                # Prepare single kandidat data
                single_data = {
                    'status': processed_data['status'],
                    'message': processed_data['message'],
                    'data': {
                        'key_pertanyaan_screening': processed_data['data']['key_pertanyaan_screening'],
                        'lowongan_pekerjaan': processed_data['data']['lowongan_pekerjaan'],
                        'kandidat': [kandidat]
                    }
                }
                
                # Updated query to include created_at
                query = """
                INSERT INTO cronjob (screening_id, data, status, created_at)
                VALUES (%s, %s, %s, NOW())
                """
                
                values = (screening_id, json.dumps(single_data), 0)
                
                cursor.execute(query, values)
                conn.commit()
                
                inserted_screening_ids.append(screening_id)  # Track this screening
                print(f"Data dengan screening_id {screening_id} berhasil disimpan ke tabel cronjob!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def get_screening_data():
    # URL endpoint
    url = "https://recruitment-ai.cbicareer.com/api/screening-ai"
    # url = "http://localhost:8000/api/screening-ai"

    # Get token from environment variable
    token = os.getenv('SACTUM_API_KEY')
    
    # Debug: print token (hapus ini nanti setelah debugging)
    # print(f"Using token: {token}")
    
    # Set up headers with bearer token
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    # Debug: print headers (hapus ini nanti setelah debugging)
    # print(f"Headers: {headers}")
    
    try:
        # Make GET request
        response = requests.get(url, headers=headers)
        
        # Check if request was successful
        if response.status_code == 200:
            print('Successfully fetched screening data from API')
            return response.json()
        else:
            return {
                'error': f'Request failed with status code: {response.status_code}',
                'message': response.text
            }
            
    except requests.exceptions.RequestException as e:
        return {
            'error': 'Request failed',
            'message': str(e)
        }

def handle_screening_event(data):
    print("Received new screening event from Pusher!")
    print(f"Data received: {data}")
    
    try:
        # Parse the JSON string if data is a string
        if isinstance(data, str):
            data = json.loads(data)
        
        # Extract jobId and userId
        job_id = data['data']['jobId']
        user_id = data['data']['userId']
        
        # API configuration
        url = "https://recruitment-ai.cbicareer.com/api/screening-ai-socket"
        # url = "http://localhost:8000/api/screening-ai-socket"
        token = os.getenv('SACTUM_API_KEY')

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        params = {
            'jobId': job_id,
            'userId': user_id
        }

        # print(f"Sending request to API:")
        # print(f"URL: {url}")
        # print(f"Headers: {headers}")
        # print(f"Params: {params}")

        # Make API request
        response = requests.get(url, headers=headers, params=params)
        # print(f"API Response Status: {response.status_code}")
        # print(f"API Response Body: {response.text}")

        if response.status_code == 200:
            response_data = response.json()
            insert_to_cronjob(response_data)
            
            print(f"Screening data inserted into cronjob table")
        else:
            print(f"API request failed: {response.status_code}")
            print(f"Error message: {response.text}")

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON data: {str(e)}")
    except KeyError as e:
        print(f"Error accessing data fields: {str(e)}")
    except requests.RequestException as e:
        print(f"Network error occurred: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

    return None

def handle_screening_delete_event(data):
    try:
        # Parse the data if it's a string
        if isinstance(data, str):
            data = json.loads(data)
            
        screening_id = data.get('data', {}).get('jobId')
        if not screening_id:
            print("Error: No jobId found in delete event data")
            return
            
        print(f"Received new screening delete data from Pusher! Screening ID: {screening_id}")

        conn = connect_to_mysql()
        cursor = conn.cursor()
        query = "DELETE FROM cronjob WHERE screening_id = %s"
        cursor.execute(query, (screening_id,))
        conn.commit()
        print(f"Successfully deleted screening with ID: {screening_id}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error in handle_screening_delete_event: {str(e)}")
        print(f"Received data: {data}")  # Log the received data for debugging

def setup_pusher():
    """Setup Pusher client dengan error handling yang lebih baik"""
    while True:
        try:
            client = PysherClient(
                key=os.getenv('PUSHER_KEY'),
                cluster=os.getenv('PUSHER_CLUSTER'),
                secret=os.getenv('PUSHER_SECRET'),
            )

            def connect_handler(data):
                try:
                    channel = client.subscribe('my-channel')
                    # channel.bind('JobVacancy_notification_screening', handle_screening_event)
                    channel.bind('JobVacancy_notification_screening_new', handle_screening_event)
                    channel.bind('JobVacancy_notification_screening_delete', handle_screening_delete_event)
                    print("Pusher listener is active and listening for screening events...")
                except Exception as e:
                    print(f"Error in connect_handler: {str(e)}")

            client.connection.bind('pusher:connection_established', connect_handler)
            client.connect()
            
            # Keep the connection alive with better error handling
            while True:
                try:
                    time.sleep(1)
                except Exception as e:
                    print(f"Error in Pusher connection: {str(e)}")
                    break  # Break inner loop to reconnect
                
        except Exception as e:
            print(f"Pusher connection failed: {str(e)}")
            time.sleep(5)  # Wait before retry
            continue  # Retry connection

def fetch_api_data():
    print("Fetching data from API...")
    result = get_screening_data()
    if isinstance(result, dict):
        if result.get('status') == False:
            # print(f"API Response: {result.get('message')}")
            pass
        else:
            insert_to_cronjob(result)
    else:
        print("Invalid response format")

def process_screening_worker():
    """Worker function untuk memproses screening di thread terpisah"""
    print("Starting screening worker...")
    while True:
        try:
            # Cek apakah ada screening yang perlu diproses
            conn = connect_to_mysql()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as count FROM cronjob WHERE status = 0")
            result = cursor.fetchone()
            pending_count = result['count']
            
            if pending_count > 0:
                print(f"Found {pending_count} pending screenings to process")
                 # process_completed_screenings
                # Pilih mode testing:
                
                # 1. Mode Testing Lengkap - Menghasilkan prompt dan menyimpan semua data
                # process_pending_screenings(Testmode=True, test_save=True)
                
                # 2. Mode Testing Prompt Saja - Hanya menghasilkan dan menyimpan prompt
                # process_pending_screenings(Testmode=True, test_save=False)
                
                # 3. Mode Produksi dengan Debug - Jalankan normal tapi simpan data
                # process_pending_screenings(Testmode=False, test_save=True)
                
                # 4. Mode Produksi - Operasi normal, tanpa data debug
                process_pending_screenings(Testmode=False, test_save=False)
                
                # Testing/Operasi Pengiriman API
                # process_completed_screenings()  # Test/jalankan pengiriman API untuk screening status=1
                
            else:
                print("No pending screenings found")
                
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"Error in screening worker: {str(e)}")
        finally:
            time.sleep(60)  # Check every minute

def process_pending_screenings(Testmode=False, test_save=False):
    """
    Memproses screening yang tertunda di database MySQL
    
    Mode Testing:
    1. Testmode=True, test_save=True
       - Menghasilkan dan menyimpan prompt ke folder 'prompt'
       - Menjalankan screening AI
       - Menyimpan data input dan hasil ke folder 'screening_ai'
       - Tidak mengubah status database
    
    2. Testmode=True, test_save=False
       - Hanya menghasilkan dan menyimpan prompt ke folder 'prompt'
       - Tidak menjalankan screening AI
       - Tidak mengubah status database
    
    3. Testmode=False, test_save=True
       - Menjalankan screening AI secara normal
       - Menyimpan data input dan hasil ke folder 'screening_ai'
       - Mengubah status database
    
    4. Testmode=False, test_save=False (Mode Produksi)
       - Menjalankan screening AI secara normal
       - Mengubah status database
       - Tidak menyimpan file debug
    
    Alur Status Database:
    - status = 0: Screening baru, belum diproses
    - status = 1: Sudah diproses oleh AI
    - status = 2: Sudah dikirim ke API
    
    Args:
        Testmode (bool): Jika True, menghasilkan dan menyimpan prompt
        test_save (bool): Jika True, menyimpan data screening dan hasilnya
    """
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor(dictionary=True)
        
        # Ambil screening dengan status = 0 (belum diproses)
        query = "SELECT * FROM cronjob WHERE status = 0"
        cursor.execute(query)
        pending_screenings = cursor.fetchall()
        
        print(f"Ditemukan {len(pending_screenings)} screening yang menunggu untuk diproses")
        
        # Buat direktori prompt jika belum ada
        prompt_dir = "prompt"
        if not os.path.exists(prompt_dir):
            os.makedirs(prompt_dir)
        
        for screening in pending_screenings:
            try:
                screening_data = json.loads(screening['data'])
                lowongan_id = screening_data['data']['lowongan_pekerjaan']['id']

                if Testmode:
                    # Mode Test: Menghasilkan dan menyimpan prompt
                    print(f"\nPrompt untuk screening {screening['screening_id']}:")
                    messages = gas_ai.generate_prompt(lowongan_id, screening_data['data'], is_simplified=False)
                    
                    # Simpan prompt ke file JSON
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"prompt_screening_{screening['screening_id']}_{timestamp}.json"
                    filepath = os.path.join(prompt_dir, filename)
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(messages, f, indent=2, ensure_ascii=False)
                    
                    print(f"Prompt disimpan ke: {filepath}")
                    print(json.dumps(messages, indent=2))
                    continue
                
                # Mode pemrosesan normal
                result = gas_ai.evaluate_candidate(screening_data, test_mode=test_save)

                if result and 'candidates' in result and len(result['candidates']) > 0:
                    candidate = result['candidates'][0]
                    # Create penilaian dictionary with default values
                    penilaian = {
                        'pendidikan': {'nilai': '0', 'uraian': 'Tidak ada penilaian'},
                        'pengalaman': {'nilai': '0', 'uraian': 'Tidak ada penilaian'},
                        'sertifikat_keahlian': {'nilai': '0', 'uraian': 'Tidak ada penilaian'},
                        'keterampilan': {'nilai': '0', 'uraian': 'Tidak ada penilaian'}
                    }
                    
                    # Update with actual values from result
                    for item in candidate['penilaian']:
                        penilaian[item['kategori']] = item
                    
                    # Define mapping for screening question categories
                    screening_categories = {
                        'operasional_kebun': 'jawaban_pertanyaan_skrining_operasional_kebun',
                        'general': 'jawaban_pertanyaan_skrining_general',
                        'pernyataan': 'jawaban_pertanyaan_skrining_pernyataan',
                        'supporting': 'jawaban_pertanyaan_skrining_supporting'
                    }
                    
                    # Prepare summary of screening questions as JSON with safe key access
                    screening_summary = {}
                    for target_key, ai_key in screening_categories.items():
                        if ai_key in penilaian:
                            screening_summary[target_key] = penilaian[ai_key]
                        else:
                            # If key doesn't exist, add empty or default value
                            screening_summary[target_key] = {
                                'kategori': ai_key,
                                'nilai': '0',
                                'uraian': 'Tidak ada penilaian'
                            }
                    
                    # Update query with all fields
                    update_query = """
                    UPDATE cronjob SET 
                        status = 1,
                        nilai_pendidikan = %s,
                        summary_pendidikan = %s,
                        nilai_pengalaman = %s,
                        sumarry_pengalaman = %s,
                        nilai_sertifikat_keahlian = %s,
                        summary_sertifikat_keahlian = %s,
                        nilai_keterampilan = %s,
                        summary_keterampilan = %s,
                        screening_key_kategori = %s,
                        summary_nilai_pertanyaan_screening = %s
                    WHERE id = %s
                    """
                    
                    update_values = (
                        int(penilaian['pendidikan']['nilai']),
                        penilaian['pendidikan']['uraian'],
                        int(penilaian['pengalaman']['nilai']),
                        penilaian['pengalaman']['uraian'],
                        int(penilaian['sertifikat_keahlian']['nilai']),
                        penilaian['sertifikat_keahlian']['uraian'],
                        int(penilaian['keterampilan']['nilai']),
                        penilaian['keterampilan']['uraian'],
                        screening_data['data']['key_pertanyaan_screening'],
                        json.dumps(screening_summary),
                        screening['id']
                    )
                    
                    cursor.execute(update_query, update_values)
                    conn.commit()
                    
                    print(f"Successfully processed screening {screening['screening_id']}")
                else:
                    print(f"Failed to process screening {screening['screening_id']}: Invalid result format")
            

            except Exception as e:
                print(f"Error processing screening {screening['screening_id']}: {str(e)}")
                continue
        
    except Exception as e:
        print(f"Database error: {str(e)}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def run_scheduler():
    """Fungsi untuk menjalankan tugas terjadwal dengan error handling"""
    print("Starting scheduler...")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            print(f"Error in scheduler: {str(e)}")
            time.sleep(5)  # Wait before continuing

if __name__ == "__main__":
    try:
        # Inisialisasi awal
        print("Starting application...")
        # fetch_api_data()  # Ambil screening baru dari API
        
        # Setup dan jalankan pusher di thread terpisah
        print("Setting up Pusher...")
        pusher_thread = Thread(target=setup_pusher, name="PusherThread")
        pusher_thread.daemon = True
        pusher_thread.start()
        
        # Jalankan worker screening di thread terpisah
        print("Setting up screening worker...")
        screening_thread = Thread(target=process_screening_worker, name="ScreeningThread")
        screening_thread.daemon = True
        screening_thread.start()
        
        # Setup scheduler
        print("Setting up scheduler...")
        schedule.every(2).minutes.do(process_completed_screenings)
        # schedule.every(5).minutes.do(fetch_api_data)
        
        # Jalankan scheduler di thread utama
        print("\nApplication started successfully!")
        print("- Screening worker is running in background")
        print("- Pusher listener is active")
        print("- Scheduler will process completed screenings every minute")
        print("- Scheduler will fetch new data every 5 minutes")
        
        run_scheduler()
        
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"\nApplication error: {str(e)}")
    finally:
        print("Application stopped")