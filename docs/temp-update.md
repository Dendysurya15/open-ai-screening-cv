# Temp Update — open-ai-screening-cv

> Catat setiap perubahan di sini. Format:
>
> ```markdown
> ## [HH:MM] Judul Singkat
> - **Files:** file1.py, file2.py
> - **Changes:** Deskripsi perubahan
> - **Type:** feature / bugfix / refactor / docs
> ```

## [Backend baru] Pindah API_BASE_URL ke career.citraborneo.co.id
- **Files:** .env
- **Changes:** Tambah `API_BASE_URL=https://career.citraborneo.co.id` (sebelumnya kosong → fallback default `cbicareer.com` web lama). Token Sanctum & endpoint `/api/screening-ai` terverifikasi sama (HTTP 200, respons `No candidates available`).
- **Type:** config
