import http.server
import json
import socketserver
import psutil

class TelemetryHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem_info = psutil.virtual_memory()
            
            metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": mem_info.percent
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
