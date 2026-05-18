import json
import time
from pysher import Pusher as PysherClient
from config.settings import PUSHER_KEY, PUSHER_CLUSTER, PUSHER_SECRET
from services.api_client import fetch_screening_by_socket
from services.database import connect_to_mysql


def insert_to_cronjob(data):
    """Insert screening data into the cronjob table for processing."""
    try:
        if isinstance(data, str):
            data = json.loads(data)

        # Normalize data format
        if "status" not in data:
            processed_data = {
                "status": True,
                "message": "Success",
                "data": data["data"],
            }
            data_list = [processed_data]
        else:
            if isinstance(data.get("data"), list):
                data_list = [
                    {"status": data["status"], "message": data["message"], "data": item}
                    for item in data["data"]
                ]
            else:
                data_list = [data]

        conn = connect_to_mysql()
        cursor = conn.cursor()

        for processed_data in data_list:
            if not processed_data.get("data"):
                continue

            kandidat_list = processed_data["data"].get("kandidat", [])
            if not kandidat_list:
                continue

            for kandidat in kandidat_list:
                screening_id = kandidat["screning_id"]

                # Check if already exists
                cursor.execute(
                    "SELECT COUNT(*) FROM cronjob WHERE screening_id = %s",
                    (screening_id,),
                )
                if cursor.fetchone()[0] > 0:
                    print(f"Screening {screening_id} sudah ada dalam database")
                    continue

                # Prepare single kandidat data
                single_data = {
                    "status": processed_data["status"],
                    "message": processed_data["message"],
                    "data": {
                        "key_pertanyaan_screening": processed_data["data"][
                            "key_pertanyaan_screening"
                        ],
                        "lowongan_pekerjaan": processed_data["data"][
                            "lowongan_pekerjaan"
                        ],
                        "kandidat": [kandidat],
                    },
                }

                query = """
                INSERT INTO cronjob (screening_id, data, status, created_at)
                VALUES (%s, %s, %s, NOW())
                """
                cursor.execute(query, (screening_id, json.dumps(single_data), 0))
                conn.commit()
                print(f"Screening {screening_id} berhasil disimpan ke cronjob")

    except Exception as e:
        print(f"Error insert_to_cronjob: {e}")
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def handle_screening_event(data):
    """Handle new screening event from Pusher."""
    print("Received new screening event from Pusher!")

    try:
        if isinstance(data, str):
            data = json.loads(data)

        job_id = data["data"]["jobId"]
        user_id = data["data"]["userId"]

        response_data = fetch_screening_by_socket(job_id, user_id)
        if response_data:
            insert_to_cronjob(response_data)
            print("Screening data inserted into cronjob table")

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {str(e)}")
    except KeyError as e:
        print(f"Error accessing data fields: {str(e)}")
    except Exception as e:
        print(f"Unexpected error in handle_screening_event: {str(e)}")


def handle_screening_delete_event(data):
    """Handle screening delete event from Pusher."""
    try:
        if isinstance(data, str):
            data = json.loads(data)

        screening_id = data.get("data", {}).get("jobId")
        if not screening_id:
            print("Error: No jobId found in delete event data")
            return

        print(f"Received delete event for screening: {screening_id}")

        conn = connect_to_mysql()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cronjob WHERE screening_id = %s", (screening_id,))
        conn.commit()
        print(f"Successfully deleted screening {screening_id}")
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error in handle_screening_delete_event: {str(e)}")


def setup_pusher():
    """Setup Pusher client with automatic reconnection."""
    while True:
        try:
            client = PysherClient(
                key=PUSHER_KEY,
                cluster=PUSHER_CLUSTER,
                secret=PUSHER_SECRET,
            )

            def connect_handler(data):
                try:
                    channel = client.subscribe("my-channel")
                    channel.bind(
                        "JobVacancy_notification_screening_new",
                        handle_screening_event,
                    )
                    channel.bind(
                        "JobVacancy_notification_screening_delete",
                        handle_screening_delete_event,
                    )
                    print("Pusher listener is active and listening for events...")
                except Exception as e:
                    print(f"Error in connect_handler: {str(e)}")

            client.connection.bind("pusher:connection_established", connect_handler)
            client.connect()

            while True:
                try:
                    time.sleep(1)
                except Exception:
                    break

        except Exception as e:
            print(f"Pusher connection failed: {str(e)}")
            time.sleep(5)
