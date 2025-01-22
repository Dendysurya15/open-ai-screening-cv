import mysql.connector

def connect_to_mysql():
    """Fungsi untuk koneksi ke database MySQL"""
    return mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",  # Sesuaikan dengan username MySQL Anda
        password="",  # Sesuaikan dengan password MySQL Anda
        database="jobvacancy_ai"
    ) 