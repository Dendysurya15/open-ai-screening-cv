import json
import time
import schedule
from threading import Thread
from services.database import connect_to_mysql
from services.ai_evaluator import evaluate_candidate
from services.api_client import (
    fetch_screening_data,
    send_screening_result,
    report_screening_failed,
)
from services.screening_intake import insert_to_cronjob, run_webhook_server
from utils.data_processor import format_screening_result
from config.settings import (
    SCHEDULER_SEND_INTERVAL,
    WORKER_SLEEP_INTERVAL,
)


def mark_screening_failed(cursor, conn, screening, error):
    """Lapor ke web (status Gagal) + tandai cronjob failed (status 9) biar tak diulang."""
    sid = screening["screening_id"]
    print(f"  ✗ Screening {sid} GAGAL: {error}")
    report_screening_failed(sid, error)
    try:
        cursor.execute("UPDATE cronjob SET status = 9 WHERE id = %s", (screening["id"],))
        conn.commit()
    except Exception as e:
        print(f"  Gagal update cronjob failed: {e}")


def fetch_api_data():
    """Fetch new screening data from API and insert into database.

    ponytail: NOT auto-run. The bulk /api/screening-ai endpoint marks ALL
    pending candidates as 'proses' on the web as a side effect, so calling it
    on every start nuked everyone to 'proses'. Push (webhook) is the source now.
    Call manually only if you need a backstop sweep for missed webhooks.
    """
    print("Fetching data from API...")
    result = fetch_screening_data()
    if isinstance(result, dict):
        if result.get("status") is False:
            pass
        elif "error" not in result:
            insert_to_cronjob(result)
    else:
        print("Invalid response format")


def process_completed_screenings():
    """Send AI-processed screenings to the API (status 1 -> status 2)."""
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM cronjob WHERE status = 1 ORDER BY created_at ASC"
        )
        completed_screenings = cursor.fetchall()

        for screening in completed_screenings:
            try:
                formatted_data = format_screening_result(
                    screening, screening["screening_id"]
                )
                if formatted_data:
                    success, response = send_screening_result(formatted_data)
                    if success:
                        cursor.execute(
                            "UPDATE cronjob SET status = 2 WHERE screening_id = %s",
                            (screening["screening_id"],),
                        )
                        conn.commit()
                        print(
                            f"Screening {screening['screening_id']} sent to API (status=2)"
                        )
                    else:
                        print(
                            f"Failed to send screening {screening['screening_id']}: {response}"
                        )
                else:
                    print(f"Failed to format screening {screening['screening_id']}")

            except Exception as e:
                print(f"Error processing screening {screening['screening_id']}: {e}")
                continue

    except Exception as e:
        print(f"Database error in process_completed_screenings: {str(e)}")
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def process_pending_screenings(test_mode=False, test_save=False):
    """Process pending screenings (status 0) with AI evaluation.

    Args:
        test_mode: If True, only generate and save prompts without AI evaluation.
        test_save: If True, save input/result data for debugging.
    """
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM cronjob WHERE status = 0")
        pending_screenings = cursor.fetchall()

        print(f"Ditemukan {len(pending_screenings)} screening yang menunggu diproses")

        for screening in pending_screenings:
            try:
                screening_data = json.loads(screening["data"])

                # Evaluate with AI
                try:
                    result = evaluate_candidate(screening_data, test_mode=test_save)
                except Exception as e:
                    mark_screening_failed(cursor, conn, screening, f"AI error: {e}")
                    continue

                if result and "candidates" in result and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]

                    # Build penilaian dict with defaults
                    penilaian = {
                        "pendidikan": {"nilai": "0", "uraian": "Tidak ada penilaian"},
                        "pengalaman": {"nilai": "0", "uraian": "Tidak ada penilaian"},
                        "sertifikat_keahlian": {
                            "nilai": "0",
                            "uraian": "Tidak ada penilaian",
                        },
                        "keterampilan": {
                            "nilai": "0",
                            "uraian": "Tidak ada penilaian",
                        },
                    }

                    for item in candidate["penilaian"]:
                        penilaian[item["kategori"]] = item

                    # Map screening question categories
                    screening_categories = {
                        "operasional_kebun": "jawaban_pertanyaan_skrining_operasional_kebun",
                        "general": "jawaban_pertanyaan_skrining_general",
                        "pernyataan": "jawaban_pertanyaan_skrining_pernyataan",
                        "supporting": "jawaban_pertanyaan_skrining_supporting",
                    }

                    screening_summary = {}
                    for target_key, ai_key in screening_categories.items():
                        if ai_key in penilaian:
                            screening_summary[target_key] = penilaian[ai_key]
                        else:
                            screening_summary[target_key] = {
                                "kategori": ai_key,
                                "nilai": "0",
                                "uraian": "Tidak ada penilaian",
                            }

                    # Update database with results
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
                        int(penilaian["pendidikan"]["nilai"]),
                        penilaian["pendidikan"]["uraian"],
                        int(penilaian["pengalaman"]["nilai"]),
                        penilaian["pengalaman"]["uraian"],
                        int(penilaian["sertifikat_keahlian"]["nilai"]),
                        penilaian["sertifikat_keahlian"]["uraian"],
                        int(penilaian["keterampilan"]["nilai"]),
                        penilaian["keterampilan"]["uraian"],
                        screening_data["data"]["key_pertanyaan_screening"],
                        json.dumps(screening_summary),
                        screening["id"],
                    )

                    cursor.execute(update_query, update_values)
                    conn.commit()
                    print(
                        f"Successfully processed screening {screening['screening_id']}"
                    )
                    print("  --- Hasil AI ---")
                    for kat in ("pendidikan", "pengalaman", "sertifikat_keahlian", "keterampilan"):
                        print(f"  {kat:20s}: {penilaian[kat]['nilai']:>3} | {penilaian[kat]['uraian']}")
                    for kat, val in screening_summary.items():
                        print(f"  [skrining] {kat:12s}: {val['nilai']:>3} | {val['uraian']}")
                    print("  ----------------")
                else:
                    mark_screening_failed(
                        cursor, conn, screening, "AI mengembalikan hasil tidak valid"
                    )

            except Exception as e:
                mark_screening_failed(cursor, conn, screening, f"Processing error: {e}")
                continue

    except Exception as e:
        print(f"Database error: {str(e)}")
    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def screening_worker():
    """Background worker that processes pending screenings periodically."""
    print("Starting screening worker...")
    while True:
        try:
            conn = connect_to_mysql()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as count FROM cronjob WHERE status = 0")
            result = cursor.fetchone()
            pending_count = result["count"]
            cursor.close()
            conn.close()

            if pending_count > 0:
                print(f"Found {pending_count} pending screenings to process")
                process_pending_screenings()
                process_completed_screenings()
            else:
                print("No pending screenings found")

        except Exception as e:
            print(f"Error in screening worker: {str(e)}")
        finally:
            time.sleep(WORKER_SLEEP_INTERVAL)


def run_scheduler():
    """Run the scheduled tasks loop."""
    print("Starting scheduler...")
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            print(f"Error in scheduler: {str(e)}")
            time.sleep(5)


def start_application():
    """Initialize and start all application components."""
    from services.database import init_database

    print("Initializing database...")
    if not init_database():
        print("Failed to initialize database. Exiting...")
        exit(1)

    print("Starting application...")

    # Webhook server thread (Laravel pushes new/delete screening here)
    print("Setting up webhook server...")
    webhook_thread = Thread(target=run_webhook_server, name="WebhookServer", daemon=True)
    webhook_thread.start()

    # Screening worker thread
    print("Setting up screening worker...")
    worker_thread = Thread(target=screening_worker, name="ScreeningWorker", daemon=True)
    worker_thread.start()

    # Scheduler setup (worker already runs in its own thread, don't duplicate)
    print("Setting up scheduler...")
    schedule.every(SCHEDULER_SEND_INTERVAL).minutes.do(process_completed_screenings)

    print("\nApplication started successfully!")
    print("- Screening worker is running in background")
    print("- Webhook server is active (push-only)")
    print(f"- Scheduler: resend results every {SCHEDULER_SEND_INTERVAL}min")

    run_scheduler()
