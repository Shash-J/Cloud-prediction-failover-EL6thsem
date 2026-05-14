import http.server
import json
import socketserver
import psutil
import time

last_net = psutil.net_io_counters()
last_time = time.time()

class TelemetryHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global last_net, last_time
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem_info = psutil.virtual_memory()
            
            current_net = psutil.net_io_counters()
            current_time = time.time()
            elapsed = current_time - last_time
            
            if elapsed > 0:
                upload_speed = (current_net.bytes_sent - last_net.bytes_sent) / elapsed
                download_speed = (current_net.bytes_recv - last_net.bytes_recv) / elapsed
            else:
                upload_speed = 0
                download_speed = 0
                
            last_net = current_net
            last_time = current_time
            
            metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": mem_info.percent,
                "upload_speed_kbps": upload_speed / 1024,
                "download_speed_kbps": download_speed / 1024,
                "process_count": len(psutil.pids())
            }
            self.wfile.write(json.dumps(metrics).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    PORT = 8081
    with socketserver.TCPServer(("", PORT), TelemetryHandler) as httpd:
        print(f"Telemetry server running on port {PORT}")
        httpd.serve_forever()
