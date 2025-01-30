# Panduan Import Model ke Ollama

## 1. Persiapan File dan Folder
1. Buat folder baru untuk model (contoh: `nama_model`)
2. Letakkan file model GGUF di folder tersebut
3. Catat nama file GGUF dengan tepat (copy-paste untuk menghindari kesalahan)

## 2. Buat Modelfile
1. Buat file baru bernama `Modelfile` (tanpa ekstensi) di folder yang sama
2. Isi Modelfile dengan template berikut:

FROM ./nama_file_model.gguf

PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER temperature 0.7
PARAMETER top_k 40
PARAMETER top_p 0.95
PARAMETER num_ctx 4096

TEMPLATE """<|im_start|>system
You are a helpful AI assistant.
<|im_end|>
<|im_start|>user
{{ .Prompt }}
<|im_end|>
<|im_start|>assistant
{{ .Response }}
<|im_end|>"""

3. Ganti `nama_file_model.gguf` dengan nama file GGUF yang sebenarnya

## 3. Import Model
1. Buka Command Prompt (CMD)
2. Pindah ke direktori model:
```bash
cd path/ke/folder/model
```

3. Jalankan perintah create:
```bash
ollama create nama_model -f Modelfile
```

## 4. Verifikasi
1. Cek apakah model sudah terinstall:
```bash
ollama list
```

2. Test model dengan perintah:
```bash
ollama run nama_model "Pesan test"
```

## Troubleshooting
Jika terjadi error:
1. Hapus model yang mungkin setengah jadi:
```bash
ollama rm nama_model
```

2. Pastikan Ollama service berjalan
3. Coba create ulang model

## Tips
- Selalu copy-paste nama file untuk menghindari typo
- Pastikan file GGUF dan Modelfile berada di folder yang sama
- Gunakan path absolut jika mengalami masalah dengan path relatif
- Backup Modelfile untuk penggunaan di masa depan

## Contoh Kasus
Misalnya untuk model Llama 3:
1. Nama file GGUF: `Meta-Llama-3.1-8B-Instruct-Q6_K_L.gguf`
2. Nama model yang diinginkan: `llama3-8b-instruct`
3. Perintah create:
```bash
ollama create llama3-8b-instruct -f Modelfile
```