from main import connect_to_mysql
import json
import requests
import os

def process_result_ai(screening_id):

    conn = connect_to_mysql()
    cursor = conn.cursor()

    # get data screening where screening_id = screening_id
    query = "SELECT * FROM screening WHERE screening_id = %s"
    cursor.execute(query, (screening_id,))
    data = cursor.fetchall()

    # save as json
    with open('screening_result.json', 'w') as f:
        json.dump(data, f)

    return data


def send_data_to_api(data):
    # get token from environment variable
    token = os.getenv('SACTUM_API_KEY')

    # send data to api
    url = "http://127.0.0.1:8000/api/result-screening-ai"
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }

    # send data to api
    response = requests.post(url, headers=headers, json=data)

    return response
