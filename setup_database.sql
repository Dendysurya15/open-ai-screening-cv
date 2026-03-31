-- Script untuk membuat database dan tabel jobvacancy_ai
-- Jalankan script ini di MySQL untuk membuat database

-- Buat database jika belum ada
CREATE DATABASE IF NOT EXISTS jobvacancy_ai;

-- Gunakan database jobvacancy_ai
USE jobvacancy_ai;

-- Buat tabel cronjob
CREATE TABLE IF NOT EXISTS cronjob (
    id INT AUTO_INCREMENT PRIMARY KEY,
    screening_id VARCHAR(255) NOT NULL UNIQUE,
    data JSON NOT NULL,
    status INT DEFAULT 0 COMMENT '0 = belum diproses, 1 = sudah diproses AI, 2 = sudah dikirim ke API',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    nilai_pendidikan INT DEFAULT 0,
    summary_pendidikan TEXT,
    nilai_pengalaman INT DEFAULT 0,
    sumarry_pengalaman TEXT COMMENT 'Note: ada typo di nama kolom ini (sumarry instead of summary)',
    nilai_sertifikat_keahlian INT DEFAULT 0,
    summary_sertifikat_keahlian TEXT,
    nilai_keterampilan INT DEFAULT 0,
    summary_keterampilan TEXT,
    screening_key_kategori VARCHAR(255),
    summary_nilai_pertanyaan_screening JSON,
    INDEX idx_screening_id (screening_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tampilkan struktur tabel
DESCRIBE cronjob;
