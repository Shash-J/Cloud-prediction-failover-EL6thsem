import http.server
import socketserver
import urllib.request
import threading
import time
import json
import os
from socketserver import ThreadingMixIn

AWS_EC2_IP = "3.83.189.73"
AWS_HTTP_URL = f"http://{AWS_EC2_IP}"
AWS_TELEMETRY_URL = f"http://{AWS_EC2_IP}:8081/metrics"

LOCAL_SIMULATION_URL = "http://localhost:8082"

USER_STATE_FILE = "user_state.json"

class State:
    routing_to = AWS_HTTP_URL
    failover_active = False
    cpu_history = []
    latest_cpu = 0
    prob_failure = 0.0
    all_metrics = []
    timeout_count = 0
    memory_percent = 0.0
    upload_speed = 0.0
    download_speed = 0.0
    process_count = 0
    # --- User State Persistence ---
    user_code = ""
    state_dirty = False

# Load persisted user state from disk on startup
if os.path.exists(USER_STATE_FILE):
    try:
        with open(USER_STATE_FILE, "r", encoding="utf-8") as f:
            _saved = json.load(f)
            State.user_code = _saved.get("code", "")
            print(f"[StateSync] Loaded saved user code from {USER_STATE_FILE} ({len(State.user_code)} chars)")
    except Exception as e:
        print(f"[StateSync] Warning: Could not load {USER_STATE_FILE}: {e}")
    
def predictor_loop():
    print("[Predictor] Starting ML monitoring loop...")
    while True:
        try:
            req = urllib.request.Request(AWS_TELEMETRY_URL)
            with urllib.request.urlopen(req, timeout=5) as response:
                State.timeout_count = 0
                data = json.loads(response.read().decode())
                cpu = data.get("cpu_percent", 0)
                State.latest_cpu = cpu
                State.memory_percent = data.get("memory_percent", 0)
                State.upload_speed = data.get("upload_speed_kbps", 0)
                State.download_speed = data.get("download_speed_kbps", 0)
                State.process_count = data.get("process_count", 0)
                
                State.cpu_history.append(cpu)
                if len(State.cpu_history) > 5:
                    State.cpu_history.pop(0)
                
                avg_cpu = sum(State.cpu_history) / len(State.cpu_history)
                prob_failure = min(100, (avg_cpu / 90.0) * 100)
                State.prob_failure = prob_failure
                
                print(f"[Predictor] AWS CPU: {cpu}% | Downtime Probability: {prob_failure:.1f}%")
                
                if prob_failure >= 90.0 and not State.failover_active:
                    print("\n" + "="*50)
                    print("!!! CRITICAL: High downtime probability!")
                    print("!!! Shifting traffic to LOCAL SIMULATION !!!")
                    print("="*50 + "\n")
                    State.routing_to = LOCAL_SIMULATION_URL
                    State.failover_active = True
                
                if prob_failure < 50.0 and State.failover_active:
                    print("\n" + "="*50)
                    print("=== RECOVERY: AWS is stable.")
                    
                    # --- "Git Push": Sync accumulated local state to AWS ---
                    if State.state_dirty and State.user_code:
                        print("=== SYNC: Pushing local user state to AWS (git-push) ===")
                        try:
                            sync_data = json.dumps({"code": State.user_code}).encode("utf-8")
                            sync_req = urllib.request.Request(
                                AWS_HTTP_URL + "/save-state",
                                data=sync_data,
                                headers={"Content-Type": "application/json"},
                                method="POST"
                            )
                            urllib.request.urlopen(sync_req, timeout=5)
                            State.state_dirty = False
                            print("=== SYNC: State pushed successfully! ===")
                        except Exception as sync_err:
                            print(f"=== SYNC WARNING: Could not push state to AWS: {sync_err} ===")
                    
                    print("=== Shifting traffic back to AWS ===")
                    print("="*50 + "\n")
                    State.routing_to = AWS_HTTP_URL
                    State.failover_active = False
                
                # Save metrics locally
                log_entry = {
                    "timestamp": time.time(),
                    "cpu_percent": cpu,
                    "probability": prob_failure,
                    "failover_active": State.failover_active,
                    "routing_to": State.routing_to,
                    "memory_percent": State.memory_percent,
                    "upload_speed_kbps": State.upload_speed,
                    "download_speed_kbps": State.download_speed,
                    "process_count": State.process_count
                }
                State.all_metrics.append(log_entry)
                try:
                    with open("metrics.json", "w") as f:
                        json.dump(State.all_metrics, f, indent=4)
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"[Predictor] Telemetry Error: {e}")
            State.timeout_count += 1
            if State.timeout_count >= 3 and not State.failover_active:
                State.latest_cpu = 100.0
                State.prob_failure = 100.0
                print("!!! CRITICAL: Telemetry timeout! Shifting traffic to LOCAL SIMULATION !!!")
                State.routing_to = LOCAL_SIMULATION_URL
                State.failover_active = True
                
        time.sleep(2)

def _save_user_state_to_disk():
    """Persist user state to disk so it survives router restarts."""
    try:
        with open(USER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"code": State.user_code}, f)
    except Exception as e:
        print(f"[StateSync] Warning: Could not write {USER_STATE_FILE}: {e}")

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Serve local index.html for initial page load (ensures auto-save code is always present).
        # Ping requests (/?ping=...) still fall through to proxy for real latency detection.
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('X-Actual-Backend-Server', State.routing_to)
            self.send_header('Access-Control-Expose-Headers', 'X-Actual-Backend-Server')
            self.end_headers()
            try:
                with open('index.html', 'rb') as f:
                    self.wfile.write(f.read())
            except Exception as e:
                self.wfile.write(f"Error loading index.html: {e}".encode())
            return

        # Intercept admin routes for the visualization dashboard
        elif self.path == '/admin/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = {
                "cpu": State.latest_cpu,
                "probability": State.prob_failure,
                "failover_active": State.failover_active,
                "routing_to": State.routing_to,
                "memory": State.memory_percent,
                "upload": State.upload_speed,
                "download": State.download_speed,
                "processes": State.process_count
            }
            self.wfile.write(json.dumps(data).encode())
            return
            
        elif self.path == '/admin':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            try:
                with open('admin_dashboard.html', 'rb') as f:
                    self.wfile.write(f.read())
            except Exception as e:
                self.wfile.write(b"admin_dashboard.html not found.")
            return
        
        # --- Load saved user state ---
        elif self.path == '/load-state':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = {"code": State.user_code}
            self.wfile.write(json.dumps(data).encode())
            return

        # Normal proxying logic
        target_url = State.routing_to + self.path
        try:
            req = urllib.request.Request(target_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                self.send_response(response.getcode())
                self.send_header('Content-type', response.info().get_content_type())
                self.send_header('X-Actual-Backend-Server', State.routing_to)
                self.send_header('Access-Control-Expose-Headers', 'X-Actual-Backend-Server')
                self.end_headers()
                self.wfile.write(response.read())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Proxy Error: {e}".encode())
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        # --- Save user state from the editor ---
        if self.path == '/save-state':
            try:
                data = json.loads(body.decode('utf-8'))
                code = data.get('code', '')
                State.user_code = code
                State.state_dirty = True
                _save_user_state_to_disk()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "saved"}).encode())
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Error saving state: {e}".encode())
            return
        
        # Proxy all other POST requests to the current backend
        target_url = State.routing_to + self.path
        try:
            req = urllib.request.Request(target_url, data=body, method='POST')
            req.add_header('Content-Type', self.headers.get('Content-Type', 'application/json'))
            with urllib.request.urlopen(req, timeout=5) as response:
                self.send_response(response.getcode())
                self.send_header('Content-type', response.info().get_content_type())
                self.send_header('X-Actual-Backend-Server', State.routing_to)
                self.end_headers()
                self.wfile.write(response.read())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Proxy Error: {e}".encode())

class ThreadedHTTPServer(ThreadingMixIn, socketserver.TCPServer):
    pass

if __name__ == "__main__":
    PORT = 8090
    
    predictor_thread = threading.Thread(target=predictor_loop, daemon=True)
    predictor_thread.start()
    
    with ThreadedHTTPServer(("", PORT), ProxyHandler) as httpd:
        print("="*60)
        print(f"Local Agentic Router & Predictor running on port {PORT}")
        print(f"1. Access your Application at: http://localhost:{PORT}")
        print(f"2. Access the Admin Dashboard at:  http://localhost:{PORT}/admin")
        print("="*60)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down...")
