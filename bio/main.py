import time
import threading
import multiprocessing
import sqlite3
from datetime import datetime
import random
import json
import os
import csv
import keyboard
import sys
from signal import signal, SIGINT
from contextlib import contextmanager

from receiver import CommandReceiver
from facial.facial_scan import FaceScanning
from finger.finger_scan import FingerScanning
from iris.iris_scan import IrisScanning

TEMP_CSV_FOLDER = "temp_csv_files"

@contextmanager
def db_connection(db_path, timeout=10):
    conn = sqlite3.connect(db_path, timeout=timeout, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
    finally:
        conn.close()

class AttendanceSystem:
    def __init__(self):
        if not os.path.exists(TEMP_CSV_FOLDER):
            os.makedirs(TEMP_CSV_FOLDER)

        self.load_config()
        self.device_ip = self.get_device_ip()
        self.device_port = self.config.get("device_port", 5000)

        self.init_databases()
        self.db_lock = threading.Lock()
        self.file_access_lock = threading.Lock()
        self.running = True

        self.receiver = CommandReceiver(self.config, self.device_ip, self.device_port, self)

        self.start_threads()

    def load_config(self):
        default_config = {
            "device_id": "DEVICE_001",
            "server_api_endpoint": "-",
            "server_hostname": "-",
            "server_ip": "127.0.0.1",
            "server_port": "5000",
            "sync_type": "periodic",
            "sync_interval": 12,
            "sync_threshold": 5,
            "authentication": {
                "facial": True,
                "finger": True,
                "iris": False
            },
            "auth_key": "abcd",
            "db_last_updated": "",
            "device_port": 5000
        }

        try:
            with open("device_config.json") as f:
                self.config = json.load(f)
        except Exception:
            self.config = default_config
            with open("device_config.json", "w") as f:
                json.dump(self.config, f, indent=2)

    def get_device_ip(self):
        return "127.0.0.1"

    def init_databases(self):
        with db_connection("employees.db") as conn:
            c = conn.cursor()
            c.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY,
                name TEXT,
                face_template BLOB,
                finger_template BLOB,
                iris_template BLOB,
                assigned_location
            )''')

            if not c.execute("SELECT COUNT(*) FROM employees").fetchone()[0]:
                sample_employees = [
                    ("E001", "Sriram", b'face1', b'finger1', b'iris1', "Location_A"),
                    ("E002", "Akhila", b'face2', b'finger2', b'iris2', "Location_B"),
                    ("E003", "Sarthak", b'face3', b'finger3', b'iris3', "Location_A")
                ]
                c.executemany('''INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)''', sample_employees)
            conn.commit()

        with db_connection("attendance_logs.db") as conn:
            c = conn.cursor()
            c.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                emp_code TEXT,
                punch_time TEXT,
                atten_type TEXT,
                device_id TEXT,
                unique_id TEXT PRIMARY KEY
            )''')
            conn.commit()

    def authenticate_employee(self):
        tasks = []
        if self.config["authentication"]["facial"]:
            tasks.append(FaceScanning.get_face_match)
        if self.config["authentication"]["finger"]:
            tasks.append(FingerScanning.get_finger_match)
        if self.config["authentication"]["iris"]:
            tasks.append(IrisScanning.get_iris_match)

        if not tasks:
            return None

        with multiprocessing.Pool(processes=len(tasks)) as pool:
            async_results = [pool.apply_async(task) for task in tasks]

            results = []
            for async_result in async_results:
                try:
                    results.append(async_result.get(timeout=5))
                except multiprocessing.TimeoutError:
                    continue

            if results and all(r == results[0] for r in results):
                return results[0]
            return None

    def log_attendance(self, emp_code, atten_type):
        unique_id = f"{self.config['device_id']}_{int(time.time()*1000)}"

        with self.db_lock:
            with db_connection("attendance_logs.db") as conn:
                c = conn.cursor()
                try:
                    c.execute('''
                    INSERT INTO logs VALUES (?, ?, ?, ?, ?)
                    ''', (
                        emp_code,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        atten_type,
                        self.config["device_id"],
                        unique_id
                    ))
                    conn.commit()
                except sqlite3.IntegrityError:
                    print(f"Duplicate entry prevented for {unique_id}")
                    conn.rollback()

    def prepare_csv_batch(self):
        with self.db_lock:
            with db_connection("attendance_logs.db") as conn:
                try:
                    c = conn.cursor()
                    c.execute("SELECT * FROM logs")
                    logs = c.fetchall()

                    if not logs:
                        return False

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    csv_file = os.path.join(TEMP_CSV_FOLDER, f"attendance_{timestamp}.csv")

                    with open(csv_file, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['emp_code', 'punch_time', 'atten_type', 'device_id', 'unique_id'])
                        writer.writerows(logs)

                    c.execute("DELETE FROM logs")
                    conn.commit()

                    print(f"[CSV] {len(logs)} logs written to {csv_file}")
                    return True

                except Exception as e:
                    print(f"[ERROR] prepare_csv_batch failed: {str(e)}")
                    conn.rollback()
                    return False

    def periodic_sync(self):
        while self.running:
            time.sleep(self.config["sync_interval"])
            self.prepare_csv_batch()

    def simulation_thread(self):
        intervals = [1, 2, 1, 1, 1, 2, 1]
        for interval in intervals:
            if not self.running:
                break
            time.sleep(interval)
            if emp_id := self.authenticate_employee():
                atten_type = random.choice(["in", "out"])
                self.log_attendance(emp_id, atten_type)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {emp_id} punched {atten_type.upper()}")

    def start_threads(self):
        if self.config["sync_type"] == "periodic":
            threading.Thread(target=self.periodic_sync, daemon=True).start()
        threading.Thread(target=self.simulation_thread, daemon=True).start()
        self.receiver.start()

    def shutdown(self):
        self.running = False
        self.prepare_csv_batch()
        if hasattr(self, 'receiver') and self.receiver:
            self.receiver.stop()
        print("System shutdown complete")

def handle_interrupt(signal_received, frame):
    print("\nShutdown requested via Ctrl+C")
    system.shutdown()
    sys.exit(0)

def key_listener(system):
    while system.running:
        if keyboard.is_pressed('/'):
            print("\nShutdown requested via '/' key")
            system.shutdown()
            os._exit(0)
        time.sleep(0.1)

if __name__ == "__main__":
    system = AttendanceSystem()
    signal(SIGINT, handle_interrupt)
    threading.Thread(target=key_listener, args=(system,), daemon=True).start()

    try:
        while system.running:
            time.sleep(1)
    except KeyboardInterrupt:
        system.shutdown()

