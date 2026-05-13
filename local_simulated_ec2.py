import http.server
import socketserver

class LocalEC2Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path.startswith('/?'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            try:
                with open('index.html', 'r', encoding='utf-8') as f:
                    content = f.read()
                
                badge = '<div style="position:fixed;bottom:20px;right:20px;background:#10b981;color:white;padding:10px 15px;border-radius:8px;font-weight:bold;z-index:9999;box-shadow:0 4px 6px rgba(0,0,0,0.3);">LOCAL FAILOVER ACTIVE - NO DOWNTIME</div>'
                content = content.replace('</body>', badge + '</body>')
                
                self.wfile.write(content.encode())
            except Exception as e:
                self.wfile.write(f"Error loading local index: {e}".encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    PORT = 8082
    with socketserver.TCPServer(("", PORT), LocalEC2Handler) as httpd:
        print(f"Local simulated EC2 running on port {PORT}")
        httpd.serve_forever()
