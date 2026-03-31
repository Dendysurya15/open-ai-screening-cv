import mysql.connector
from mysql.connector import Error

def init_database():
    """Fungsi untuk membuat database dan tabel jika belum ada"""
    try:
        # Koneksi ke MySQL tanpa specify database
        conn = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="root",
            password=""
        )
        cursor = conn.cursor()

        # Buat database jika belum ada
        cursor.execute("CREATE DATABASE IF NOT EXISTS jobvacancy_ai")
        print("Database 'jobvacancy_ai' sudah siap")

        # Gunakan database
        cursor.execute("USE jobvacancy_ai")

        # Buat tabel cronjob jika belum ada
        create_table_query = """
        CREATE TABLE IF NOT EXISTS cronjob (
            id INT AUTO_INCREMENT PRIMARY KEY,
            screening_id VARCHAR(255) NOT NULL UNIQUE,
            data JSON NOT NULL,
            status INT DEFAULT 0 COMMENT '0 = belum diproses, 1 = sudah diproses AI, 2 = sudah dikirim ke API',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            nilai_pendidikan INT DEFAULT 0,
            summary_pendidikan TEXT,
            nilai_pengalaman INT DEFAULT 0,
            sumarry_pengalaman TEXT COMMENT 'Note: ada typo di nama kolom ini',
            nilai_sertifikat_keahlian INT DEFAULT 0,
            summary_sertifikat_keahlian TEXT,
            nilai_keterampilan INT DEFAULT 0,
            summary_keterampilan TEXT,
            screening_key_kategori VARCHAR(255),
            summary_nilai_pertanyaan_screening JSON,
            INDEX idx_screening_id (screening_id),
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        cursor.execute(create_table_query)
        print("Tabel 'cronjob' sudah siap")

        cursor.close()
        conn.close()
        return True

    except Error as e:
        print(f"Error saat inisialisasi database: {e}")
        return False

def connect_to_mysql():
    """Fungsi untuk koneksi ke database MySQL"""
    return mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",  # Sesuaikan dengan username MySQL Anda
        password="",  # Sesuaikan dengan password MySQL Anda
        database="jobvacancy_ai"
    ) 