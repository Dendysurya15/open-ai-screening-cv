# SYSTEM GUIDE — open-ai-screening-cv

**Versi Dokumen:** 0.2.0

CV Screening AI — evaluasi kandidat otomatis pakai Ollama LLM (lokal).

## Alur

1. Webhook server (`:8473`) terima push `new`/`delete` dari web Laravel (`X-Webhook-Token`).
2. Push `new` → fetch detail via `/api/screening-ai-socket` → simpan ke `cronjob` (status 0).
3. Worker evaluasi kandidat via Ollama (input: pertanyaan+jawaban di-zip, prompt ketat).
4. Sukses → `POST /api/result-screening-ai`. Gagal → `POST /api/screening-ai-failed` (status Gagal).

Entry point: `main.py` → `services.scheduler.start_application()`. Jalankan: `.\run.ps1` (conda `openai` + watchfiles auto-reload).

## Struktur

| Path | Isi |
|------|-----|
| `main.py` | Entry point |
| `run.ps1` | Aktifkan env conda `openai` + watch auto-reload |
| `config/settings.py` | Konfigurasi (env): API, webhook host/port/token, Ollama, DB |
| `config/prompt_ai.json` | Prompt template AI (rubrik + `aturan_wajib`) |
| `services/scheduler.py` | Orkestrasi (worker thread + schedule resend) |
| `services/api_client.py` | Client API: fetch, kirim hasil, lapor gagal |
| `services/screening_intake.py` | Webhook HTTP server (ganti Pusher) |
| `services/ai_evaluator.py` | Build prompt + request Ollama + evaluasi |
| `services/database.py` | Akses DB (`cronjob`) |
| `utils/` | data_processor (zip Q+A), ollama_ai, response_parser |

## Env (`.env`)

`API_BASE_URL`, `SACTUM_API_KEY`, `WEBHOOK_PORT` (8473), `WEBHOOK_TOKEN`, `OLLAMA_MODEL` (`qwen2.5:7b`), `DB_*`.

## Changelog

### [0.2.0] - 2026-06-30 - Webhook + kualitas AI
- **Ganti Pusher → webhook HTTP** (`screening_intake.py`): balas 202 lalu fetch+queue di thread. Hapus `pusher_listener.py` & dep `pysher`.
- **Push-only**: tak auto-bulk-fetch saat start (cegah semua kandidat ter-mark "proses").
- **Lapor gagal**: `report_screening_failed` di 3 titik kegagalan eval → web set status Gagal.
- **Kualitas AI**: zip teks pertanyaan+jawaban skrining; prompt ketat (kategori inti wajib 1-5+uraian, larang 0/kosong).
- `run.ps1` + hasil AI tampil di log.

### [0.1.0] - 2026-06-30 - Init docs
- Tambah struktur `docs/` (SYSTEM_GUIDE, temp-update, REMINDER-BUG-FIX, BUG-SOLVED, QA-MANUAL-CHECK).
