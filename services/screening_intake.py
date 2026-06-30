"""Screening intake — HTTP webhook server.

Replaces the old Pusher listener. The Laravel web (jobvacancy-cbi) now pushes
directly to this server over the internal network:

    POST /screening/new     body: {"jobId": <id>, "userId": <id>}
    POST /screening/delete  body: {"jobId": <screening_id>}

Both require header  X-Webhook-Token: <WEBHOOK_TOKEN>.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from config.settings import WEBHOOK_HOST, WEBHOOK_PORT, WEBHOOK_TOKEN
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


def handle_new(job_id, user_id):
    """Fetch full screening data for a job/user and queue it."""
    response_data = fetch_screening_by_socket(job_id, user_id)
    if response_data:
        insert_to_cronjob(response_data)
        print(f"Screening for job={job_id} user={user_id} inserted into cronjob")


def handle_delete(screening_id):
    """Remove a queued screening from cronjob."""
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cronjob WHERE screening_id = %s", (screening_id,))
        conn.commit()
        print(f"Deleted screening {screening_id} from cronjob")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error handle_delete: {e}")


class _Handler(BaseHTTPRequestHandler):
    def _reply(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # Auth at trust boundary — reject anything without the shared token.
        if WEBHOOK_TOKEN and self.headers.get("X-Webhook-Token") != WEBHOOK_TOKEN:
            return self._reply(401, {"status": False, "message": "Unauthorized"})

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or "{}")
        except (ValueError, json.JSONDecodeError):
            return self._reply(400, {"status": False, "message": "Invalid JSON"})

        if self.path == "/screening/new":
            job_id, user_id = body.get("jobId"), body.get("userId")
            if not job_id or not user_id:
                return self._reply(422, {"status": False, "message": "jobId & userId required"})
            # Reply first, then fetch+queue in a thread. handle_new() calls back
            # to Laravel — if we block here, single-threaded `artisan serve` can't
            # answer that callback and times out (WinError 10053).
            self._reply(202, {"status": True, "message": "Accepted"})
            Thread(target=handle_new, args=(job_id, user_id), daemon=True).start()
            return

        if self.path == "/screening/delete":
            screening_id = body.get("jobId")
            if not screening_id:
                return self._reply(422, {"status": False, "message": "jobId required"})
            handle_delete(screening_id)
            return self._reply(200, {"status": True, "message": "Deleted"})

        return self._reply(404, {"status": False, "message": "Not found"})

    def log_message(self, *args):
        pass  # ponytail: silence default per-request stderr logging


def run_webhook_server():
    """Run the blocking webhook HTTP server (call in its own thread)."""
    server = ThreadingHTTPServer((WEBHOOK_HOST, WEBHOOK_PORT), _Handler)
    print(f"Webhook server listening on {WEBHOOK_HOST}:{WEBHOOK_PORT}")
    server.serve_forever()
