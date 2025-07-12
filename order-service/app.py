from flask import Flask, request, jsonify
import uuid
import mysql.connector
from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable
import json
import os
import time
import traceback

app = Flask(__name__)

# ⏳ Inisialisasi KafkaProducer dengan retry saat Redpanda belum siap
producer = None
for attempt in range(5):
    try:
        producer = KafkaProducer(
            bootstrap_servers=os.getenv("REDPANDA_BROKER", "redpanda:9092"),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print("✅ Kafka Producer berhasil terkoneksi!")
        break
    except NoBrokersAvailable:
        print(f"❌ Kafka belum tersedia, coba lagi ({attempt + 1}/5)...")
        time.sleep(3)
    except Exception as e:
        print("❌ Gagal konek Kafka:", e)
        time.sleep(3)

@app.route('/orders', methods=['POST'])
def create_order():
    data = request.json
    user_id = data.get("user_id", str(uuid.uuid4()))
    price = data.get("price")
    qty = data.get("qty")
    total = data.get("total")

    status = False
    try:
        db = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "mysql"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", "root"),
            database=os.getenv("MYSQL_DATABASE", "orders")
        )
        cursor = db.cursor()
        cursor.execute("INSERT INTO orders (user_id, price, qty, total) VALUES (%s, %s, %s, %s)",
                       (user_id, price, qty, total))
        db.commit()
        db.close()
        status = True
        print("✅ Data berhasil disimpan ke MySQL.")
    except Exception as e:
        print("❌ DB Error:", e)
        traceback.print_exc()

    message = {
        "user_id": user_id,
        "price": price,
        "qty": qty,
        "total": total,
        "status": status
    }

    try:
        if producer:
            producer.send("order-topic", message)
            print("✅ Pesan dikirim ke Kafka.")
        else:
            print("❌ Kafka Producer belum siap, pesan tidak dikirim.")
    except KafkaError as e:
        print("❌ Kafka Send Error:", e)
        traceback.print_exc()

    return jsonify(message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
