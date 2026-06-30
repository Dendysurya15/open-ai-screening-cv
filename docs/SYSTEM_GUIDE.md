# SYSTEM GUIDE — open-ai-screening-cv

**Versi Dokumen:** 0.1.0

CV Screening AI — evaluasi kandidat otomatis pakai Ollama LLM (lokal).

## Alur

1. Fetch data screening pending dari API recruitment.
2. Dengarkan event real-time via Pusher.
3. Evaluasi kandidat pakai model Ollama.
4. Kirim hasil balik ke API.

Entry point: `main.py` → `services.scheduler.start_application()`.

## Struktur

| Path | Isi |
|------|-----|
| `main.py` | Entry point |
| `config/settings.py` | Konfigurasi (env) |
| `config/prompt_ai.json` | Prompt template AI |
| `services/scheduler.py` | Orkestrasi (schedule + worker) |
| `services/api_client.py` | Client API recruitment |
| `services/pusher_listener.py` | Listener event real-time |
| `services/ai_evaluator.py` | Evaluasi kandidat |
| `services/database.py` | Akses DB |
| `utils/` | Helper: data_processor, ollama_ai, response_parser, dll |
| `setup_database.sql` | Skema DB awal |

## Changelog

### [0.1.0] - 2026-06-30 - Init docs
- Tambah struktur `docs/` (SYSTEM_GUIDE, temp-update, REMINDER-BUG-FIX, BUG-SOLVED, QA-MANUAL-CHECK).
