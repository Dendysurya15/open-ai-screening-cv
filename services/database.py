import mysql.connector
from mysql.connector import Error
from config.settings import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


def init_database():
    """Create database and tables if they don't exist."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cursor = conn.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        print(f"Database '{DB_NAME}' sudah siap")

        cursor.execute(f"USE {DB_NAME}")

        create_table_query = """
        CREATE TABLE IF NOT EXISTS cronjob (
            id INT AUTO_INCREMENT PRIMARY KEY,
            screening_id VARCHAR(255) NOT NULL UNIQUE,
            data JSON NOT NULL,
            status INT DEFAULT 0 COMMENT '0=pending, 1=processed by AI, 2=sent to API',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            nilai_pendidikan INT DEFAULT 0,
            summary_pendidikan TEXT,
            nilai_pengalaman INT DEFAULT 0,
            sumarry_pengalaman TEXT,
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
    """Get a MySQL connection to the application database."""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )
