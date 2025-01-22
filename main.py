import requests
import os
import mysql.connector
import json
from dotenv import load_dotenv
import schedule
import time
from threading import Thread
from pysher import Pusher as PysherClient
import gas_ai
from datetime import datetime
# from process_result_ai import process_result_ai
# Load environment variables
load_dotenv()

def connect_to_mysql():
    return mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",  # Sesuaikan dengan username MySQL Anda
        password="",  # Sesuaikan dengan password MySQL Anda
        database="jobvacancy_ai"
    )

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
        
        # Process newly inserted screenings immediately
        if inserted_screening_ids:
            print("Processing newly inserted screenings...")
            process_pending_screenings()
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def get_screening_data():
    # URL endpoint
    url = "http://127.0.0.1:8000/api/screening-ai"
    
    # Get token from environment variable
    token = os.getenv('SACTUM_API_KEY')
    
    # Debug: print token (hapus ini nanti setelah debugging)
    print(f"Using token: {token}")
    
    # Set up headers with bearer token
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    # Debug: print headers (hapus ini nanti setelah debugging)
    print(f"Headers: {headers}")
    
    try:
        # Make GET request
        response = requests.get(url, headers=headers)
        
        # Check if request was successful
        if response.status_code == 200:
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
    print("Received new screening data from Pusher!")
    insert_to_cronjob(data)

def setup_pusher():
    client = PysherClient(
        key=os.getenv('PUSHER_KEY'),
        cluster=os.getenv('PUSHER_CLUSTER')
    )

    def connect_handler(data):
        channel = client.subscribe('my-channel')
        channel.bind('JobVacancy_notification_screening', handle_screening_event)
        print("Pusher listener is active and listening for screening events...")

    client.connection.bind('pusher:connection_established', connect_handler)
    client.connect()
    
    # Keep the connection alive
    while True:
        time.sleep(1)

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

def process_pending_screenings(Testmode=False, limit=None):
    """
    Process pending screenings in the MySQL database
    Args:
        Testmode (bool): If True, only generate and save prompts without processing
        limit (int): Maximum number of screenings to process. None for no limit
    """
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor(dictionary=True)
        
        # Modify query to include LIMIT if specified
        query = "SELECT * FROM cronjob WHERE status = 0"
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        pending_screenings = cursor.fetchall()
        
        print(f"Found {len(pending_screenings)} pending screenings to process")
        
        # Create prompt directory if it doesn't exist
        prompt_dir = "prompt"
        if not os.path.exists(prompt_dir):
            os.makedirs(prompt_dir)
        
        for screening in pending_screenings:
            try:
                screening_data = json.loads(screening['data'])
                lowongan_id = screening_data['data']['lowongan_pekerjaan']['id']

                if Testmode:
                    print(f"\nPrompt for screening {screening['screening_id']}:")
                    messages = gas_ai.generate_prompt(lowongan_id, screening_data['data'], is_simplified=False)
                    
                    # Simpan prompt ke file JSON dalam folder prompt
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"prompt_screening_{screening['screening_id']}_{timestamp}.json"
                    filepath = os.path.join(prompt_dir, filename)
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(messages, f, indent=2, ensure_ascii=False)
                    
                    print(f"Prompt telah disimpan ke file: {filepath}")
                    print(json.dumps(messages, indent=2))  # Tetap menampilkan di console
                    continue
                
                # Normal processing mode
                result = gas_ai.evaluate_candidate(screening_data['data'])

                # save result as json
                # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # filename = f"output_{screening['screening_id']}_{timestamp}.json"
                # filepath = os.path.join(prompt_dir, filename)
                # with open(filepath, 'w', encoding='utf-8') as f:
                #     json.dump(result, f, indent=2, ensure_ascii=False)
                
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
                    
                    # # Save to JSON file (keeping existing functionality)
                    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    # output_filename = f"output_{screening['screening_id']}_{timestamp}.json"
                    # with open(output_filename, 'w', encoding='utf-8') as f:
                    #     json.dump(result, f, indent=2, ensure_ascii=False)
                    
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

def format_screening_result(screening_data, screening_id):
    """Format screening data to match required API format"""
    try:
        key_screening = screening_data['screening_key_kategori'].split(',')
        summary_screening = json.loads(screening_data['summary_nilai_pertanyaan_screening'])
        
        # Initialize result structure
        result = {
            "data": {
                "identities": {
                    "1": {
                        "kategori": "pendidikan",
                        "score": str(screening_data['nilai_pendidikan']),
                        "comment": screening_data['summary_pendidikan']
                    },
                    "2": {
                        "kategori": "pengalaman",
                        "score": str(screening_data['nilai_pengalaman']),
                        "comment": screening_data['sumarry_pengalaman']
                    }
                },
                "screening": {}
            },
            "screening_id": str(screening_id)
        }
        
        # Map category names to numbers
        category_mapping = {
            'supporting': '2',
            'general': '3',
            'pernyataan': '4',
            'operasional_kebun': '5'
        }
        
        # Add screening data with numbered keys
        for category in key_screening:
            category = category.strip()  # Remove any whitespace
            if category in summary_screening:
                category_data = summary_screening[category]
                number = category_mapping.get(category, '0')
                
                result['data']['screening'][number] = {
                    "kategori": category_data['kategori'],
                    "score": str(category_data['nilai']),
                    "comment": category_data['uraian']
                }
        
        return result
    except Exception as e:
        print(f"Error formatting screening result: {str(e)}")
        return None

def send_to_api(formatted_data):
    """Send formatted data to API endpoint"""
    api_url = os.getenv('API_ENDPOINT', 'http://127.0.0.1:8000/api/result-screening-ai')
    headers = {
        'Authorization': f"Bearer {os.getenv('SACTUM_API_KEY')}",
        'Content-Type': 'application/json'
    }
    
    try:
        # Save the request data to a JSON file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"api_request_{formatted_data['screening_id']}_{timestamp}.json"
        
        # Create 'api_requests' directory if it doesn't exist
        if not os.path.exists('api_requests'):
            os.makedirs('api_requests')
            
        filepath = os.path.join('api_requests', filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)
        
        print(f"API request data saved to: {filepath}")
        
        # Send the actual request
        response = requests.post(api_url, json=formatted_data, headers=headers)
        return response.status_code == 200, response.text
    except Exception as e:
        print(f"Error sending to API: {str(e)}")
        return False, str(e)

def process_completed_screenings():
    """Process and send completed screening results"""
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor(dictionary=True)
        
        # Get screenings with status = 2 (completed but not sent)
        query = "SELECT * FROM cronjob WHERE status = 1"
        cursor.execute(query)
        completed_screenings = cursor.fetchall()
        
        print(f"Found {len(completed_screenings)} completed screenings to send to API")
        
        for screening in completed_screenings:
            try:
                # Format the data for API
                formatted_data = format_screening_result(screening['data'], screening['screening_id'])
                if formatted_data:
                    # Send to API
                    success, response = send_to_api(formatted_data)
                    if success:
                        # # Update status to 3 (sent to API)
                        # update_query = "UPDATE cronjob SET status = 2 WHERE screening_id = %s"
                        # cursor.execute(update_query, (screening['screening_id'],))
                        # conn.commit()
                        print(f"Successfully sent screening {screening['screening_id']} to API")
                    else:
                        print(f"Failed to send screening {screening['screening_id']} to API: {response}")
                else:
                    print(f"Failed to format screening {screening['screening_id']} data")
                
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
    schedule.every(1).minutes.do(process_completed_screenings)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # Initial runs
    # fetch_api_data()
    # process_completed_screenings()
    # # process_pending_screenings(Testmode=True, limit=1)
    process_pending_screenings(Testmode=False)
    
    # Setup and run pusher in separate thread
    pusher_thread = Thread(target=setup_pusher)
    pusher_thread.daemon = True
    pusher_thread.start()
    
    # Run scheduler in main thread
    print("Starting scheduler - will process and send completed screenings every minute")
    run_scheduler()