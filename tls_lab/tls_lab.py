from http.server import HTTPServer, BaseHTTPRequestHandler
import ssl 

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/hello':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            response_text = "Hello from Vasyliuk Margarita KP-32"
            self.wfile.write(response_text.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

port = 4433 
httpd = HTTPServer(('localhost', port), SimpleHTTPRequestHandler)

context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

context.minimum_version = ssl.TLSVersion.TLSv1_2
context.maximum_version = ssl.TLSVersion.TLSv1_2

context.set_ciphers('AES128-SHA256:AES256-SHA')

context.load_cert_chain(certfile="localhost.pem", keyfile="localhost-key.pem")

httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

print(f"Secure HTTPS server is running on https://localhost:{port}/hello")
httpd.serve_forever()