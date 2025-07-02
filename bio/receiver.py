import socket
import threading
import json
import time

class CommandReceiver:
    def __init__(self, config, device_ip, device_port, system):
        self.device_ip = device_ip
        self.device_port = device_port
        self.auth_key = config.get("auth_key", "")
        self.system = system
        self.running = True
        self.server_thread = threading.Thread(target=self.run_server, daemon=True)

    def start(self):
        self.server_thread.start()

    def stop(self):
        self.running = False

    def run_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.device_ip, self.device_port))
            server_socket.listen(5)
            print(f"[Receiver] Listening at {self.device_ip}:{self.device_port}")

            while self.running:
                try:
                    client_socket, addr = server_socket.accept()
                    threading.Thread(target=self.handle_client, args=(client_socket, addr), daemon=True).start()
                except Exception as e:
                    print(f"[Receiver] Connection error: {e}")

    def handle_client(self, client_socket, addr):
        try:
            with client_socket:
                data = client_socket.recv(4096)
                if not data:
                    return
                try:
                    command = json.loads(data.decode("utf-8"))
                    print(f"[Receiver] Received: {command}")
                    response = self.process_command(command)
                    client_socket.send(json.dumps(response).encode())
                except json.JSONDecodeError:
                    client_socket.send(b'{"error": "Invalid JSON"}')
        except Exception as e:
            print(f"[Receiver] Client error: {e}")

    def process_command(self, command):
        try:
            if command.get("auth_key") != self.auth_key:
                return {"status": "error", "message": "Invalid auth_key"}

            cmd_type = command.get("type")
            payload = command.get("payload", {})

            if cmd_type == "update_employee":
                success = self.system.update_employee(
                    payload.get("employee_id"),
                    payload.get("new_data")
                )
                return {"status": "success" if success else "error"}

            elif cmd_type == "delete_employee":
                success = self.system.delete_employee(payload.get("employee_id"))
                return {"status": "success" if success else "error"}

            elif cmd_type == "sync_now":
                self.system.prepare_csv_batch()
                return {"status": "success", "message": "Sync triggered"}

            else:
                return {"status": "error", "message": "Unknown command type"}

        except Exception as e:
            return {"status": "error", "message": str(e)}
