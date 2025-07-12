import os
import json
import requests
from kafka import KafkaConsumer
import logging
from datetime import datetime

# Konfigurasi logging untuk output yang jelas
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.info("▶ Script consumer.py dimulai.")

# Ambil konfigurasi dari environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
KAFKA_BROKER_URL = os.getenv('KAFKA_BROKER_URL') # Tidak perlu nilai default jika di-set di docker-compose

logging.debug(f"SUPABASE_URL: {SUPABASE_URL}")
logging.debug(f"SUPABASE_KEY: {'<HIDDEN>' if SUPABASE_KEY else 'None'}")
logging.debug(f"KAFKA_BROKER_URL: {KAFKA_BROKER_URL}")

# Hentikan script jika variabel penting tidak ada
if not SUPABASE_URL or not SUPABASE_KEY or not KAFKA_BROKER_URL:
    logging.error("FATAL: Pastikan variabel lingkungan SUPABASE_URL, SUPABASE_KEY, dan KAFKA_BROKER_URL sudah di-set!")
    exit(1)

# Inisialisasi Kafka Consumer dengan penanganan error
try:
    consumer = KafkaConsumer(
        'order-topic',
        bootstrap_servers=[KAFKA_BROKER_URL],
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='supabase-logger-group',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    logging.info("✅ KafkaConsumer berhasil terhubung.")
except Exception as e:
    logging.error(f"FATAL: Gagal menginisialisasi KafkaConsumer: {e}")
    exit(1)

# Siapkan headers untuk request ke Supabase
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

logging.info("... Menunggu pesan dari topic 'order-topic' ...")
for msg in consumer:
    try:
        data = msg.value
        logging.info(f"⬇ Pesan diterima: {data}")

        # Siapkan payload untuk dikirim sebagai log ke Supabase
        log_payload = {
            "topic": msg.topic,
            "message": json.dumps(data),
            "sender": "my-flask-api",
            "created_at": datetime.utcnow().isoformat(),
            "status": data.get("status", False)
        }

        logging.debug(f"📦 Mengirim log ke Supabase: {log_payload}")

        # Kirim data ke Supabase
        response = requests.post(SUPABASE_URL, headers=headers, json=log_payload)
        
        # Cek status response dari Supabase
        response.raise_for_status() # Akan error jika status code 4xx atau 5xx
        
        logging.info(f"✅ Berhasil dikirim ke Supabase. Status: {response.status_code}")

    except json.JSONDecodeError as e:
        logging.error(f"⚠ Gagal mem-parsing pesan JSON: {msg.value}. Error: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"⚠ Gagal mengirim data ke Supabase: {e}")
        # Coba tampilkan response body jika ada, untuk membantu debug
        if 'response' in locals() and response.text:
             logging.error(f"Response Body dari Supabase: {response.text}")
    except Exception as e:
        logging.error(f"Terjadi error yang tidak terduga: {e}")