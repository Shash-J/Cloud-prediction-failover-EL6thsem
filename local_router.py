import http.server
import socketserver
import urllib.request
import threading
import time
import json
from socketserver import ThreadingMixIn

AWS_EC2_IP = "3.83.189.73"
AWS_HTTP_URL = f"http://{AWS_EC2_IP}"
AWS_TELEMETRY_URL = f"http://{AWS_EC2_IP}:8081/metrics"

LOCAL_SIMULATION_URL = "http://localhost:8082"

class State:
    routing_to = AWS_HTTP_URL
    failover_active = False
    cpu_history = []
    latest_cpu = 0
    prob_failure = 0.0
    all_metrics = []
    timeout_count = 0
    
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
                    print("=== Syncing data and shifting traffic back to AWS ===")
                    print("="*50 + "\n")
                    State.routing_to = AWS_HTTP_URL
                    State.failover_active = False
                
                # Save metrics locally
                log_entry = {
                    "timestamp": time.time(),
                    "cpu_percent": cpu,
                    "probability": prob_failure,
                    "failover_active": State.failover_active,
                    "routing_to": State.routing_to
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

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Intercept admin routes for the visualization dashboard
        if self.path == '/admin/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = {
                "cpu": State.latest_cpu,
                "probability": State.prob_failure,
                "failover_active": State.failover_active,
                "routing_to": State.routing_to
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
