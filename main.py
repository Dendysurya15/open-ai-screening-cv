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
        # Jika data adalah string JSON, parse terlebih dahulu
        if isinstance(data, str):
            data = json.loads(data)
        
        # Jika tidak ada key 'status', berarti data dari pusher
        if 'status' not in data:
            processed_data = {
                'status': True,
                'message': 'Success',
                'data': data['data']
            }
        else:
            processed_data = data

        # Cek apakah ada data
        if not processed_data.get('data'):
            print("Tidak ada data untuk diproses")
            return
            
        conn = connect_to_mysql()
        cursor = conn.cursor()
        
        # Cek struktur data kandidat
        if 'kandidat' not in processed_data['data'] or not processed_data['data']['kandidat']:
            print("Tidak ada data kandidat yang tersedia")
            return
            
        # Mengakses screening_id dari struktur yang benar
        screening_id = processed_data['data']['kandidat'][0]['screning_id']
        
        # Cek apakah screening_id sudah ada
        if check_screening_exists(cursor, screening_id):
            print(f"Data dengan screening_id {screening_id} sudah ada dalam database!")
            return
        
        # Query untuk insert data
        query = """
        INSERT INTO cronjob (screening_id, data, status)
        VALUES (%s, %s, %s)
        """
        
        # Siapkan values
        json_data = json.dumps(processed_data)
        status = 0  # Status 0 berarti belum diproses AI
        
        values = (screening_id, json_data, status)
        
        cursor.execute(query, values)
        conn.commit()
        
        print(f"Data dengan screening_id {screening_id} berhasil disimpan ke tabel cronjob!")
        
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
            print(f"API Response: {result.get('message')}")
        else:
            insert_to_cronjob(result)
    else:
        print("Invalid response format")

def process_pending_screenings():
    """Process all pending screenings in the MySQL database"""
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor(dictionary=True)  # Use dictionary cursor for easier data handling
        
        # Get all unprocessed screenings (status = 0)
        query = "SELECT * FROM cronjob WHERE status = 0"
        cursor.execute(query)
        pending_screenings = cursor.fetchall()
        
        print(f"Found {len(pending_screenings)} pending screenings to process")
        
        for screening in pending_screenings:
            try:
                # Parse the JSON data
                screening_data = json.loads(screening['data'])
                
                # Process the screening using gas_ai
                result = gas_ai.evaluate_candidate(screening_data['data'])
                
                if result:
                    # Save the result to a JSON file with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_filename = f"output_{screening['screening_id']}_{timestamp}.json"
                    
                    with open(output_filename, 'w', encoding='utf-8') as f:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    
                    # Update the status in database
                    update_query = "UPDATE cronjob SET status = 1 WHERE id = %s"
                    cursor.execute(update_query, (screening['id'],))
                    conn.commit()
                    
                    print(f"Successfully processed screening {screening['screening_id']}, output saved to {output_filename}")
                else:
                    print(f"Failed to process screening {screening['screening_id']}")
            
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
    schedule.every(15).minutes.do(fetch_api_data)
    schedule.every(5).minutes.do(process_pending_screenings)  # Add screening processing to scheduler
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # Initial runs
    fetch_api_data()
    process_pending_screenings()
    
    # Setup and run pusher in separate thread
    pusher_thread = Thread(target=setup_pusher)
    pusher_thread.daemon = True
    pusher_thread.start()
    
    # Run scheduler in main thread
    print("Starting scheduler - will fetch data every 15 minutes and process screenings every 5 minutes")
    run_scheduler()