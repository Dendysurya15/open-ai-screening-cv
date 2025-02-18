# Add these lines at the top to handle imports from parent directory
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import connect_to_mysql
from datetime import datetime
import json
import requests
import argparse

def format_screening_result(screening_data, screening_id):
    """Format screening data to match required API format"""
    try:
        # Get and parse the screening data
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
        
        # Map category names to numbers and their corresponding keys
        category_mapping = {
            'operasional_kebun': {
                'number': '1',
                'key': 'jawaban_pertanyaan_skrining_operasional_kebun'
            },
            'general': {
                'number': '3',
                'key': 'jawaban_pertanyaan_skrining_general'
            },
            'pernyataan': {
                'number': '4',
                'key': 'jawaban_pertanyaan_skrining_pernyataan'
            },
            'supporting': {
                'number': '2',
                'key': 'jawaban_pertanyaan_skrining_supporting'
            },
        }
        
        # Add screening data with numbered keys
        for category in key_screening:
            category = category.strip()  # Remove any whitespace
            if category in summary_screening:
                category_data = summary_screening[category]
                # Skip if nilai is "0" and uraian is "Tidak ada penilaian"
                if category_data['nilai'] == "0" and category_data['uraian'] == "Tidak ada penilaian":
                    continue
                    
                mapping = category_mapping.get(category)
                if mapping:
                    result['data']['screening'][mapping['number']] = {
                        "kategori": mapping['key'],
                        "score": str(category_data['nilai']),
                        "comment": category_data['uraian']
                    }
        
        # Debug print
        # print("Formatted result:")
        # print(json.dumps(result, indent=2))
        
        return result
    except Exception as e:
        print(f"Error formatting screening result: {str(e)}")
        return None


def send_to_api(formatted_data):
    """Send formatted data to API endpoint"""
    api_url = os.getenv('API_ENDPOINT', 'https://cbicareer.com/api/result-screening-ai')
    # api_url = "http://localhost:8000/api/result-screening-ai"

    headers = {
        'Authorization': f"Bearer {os.getenv('SACTUM_API_KEY')}",
        'Content-Type': 'application/json'
    }
    
    try:
        # Save the request data to a JSON file
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # filename = f"api_request_{formatted_data['screening_id']}_{timestamp}.json"
        
        # # Create 'api_requests' directory if it doesn't exist
        # if not os.path.exists('api_requests'):
        #     os.makedirs('api_requests')
            
        # filepath = os.path.join('api_requests', filename)
        # with open(filepath, 'w', encoding='utf-8') as f:
        #     json.dump(formatted_data, f, indent=2, ensure_ascii=False)
        
        # print(f"API request data saved to: {filepath}")
        
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
        
        # Get screenings with status = 1 (screened by AI but not sent to API)
        query = """
        SELECT * FROM cronjob 
        WHERE status = 1 
        ORDER BY created_at ASC
        """
        cursor.execute(query)
        completed_screenings = cursor.fetchall()
        
        # print(f"Found {len(completed_screenings)} AI-screened results to send to API")
        
        for screening in completed_screenings:
            try:
                # Format the data for API
                formatted_data = format_screening_result(screening, screening['screening_id'])
                if formatted_data:
                    # Send to API
                    success, response = send_to_api(formatted_data)
                    if success:
                        # Update status to 2 (sent to API successfully)
                        update_query = "UPDATE cronjob SET status = 2 WHERE screening_id = %s"
                        cursor.execute(update_query, (screening['screening_id'],))
                        conn.commit()
                        print(f"Successfully sent screening {screening['screening_id']} to API and updated status to 2")
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

