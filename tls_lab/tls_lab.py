import ssl
import json
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

CASDOOR_URL = "http://localhost:8000"
CLIENT_ID = "7a300b59b0a8c24bba9e"
CLIENT_SECRET = "3e8b1ee3545fed5c0bf475d3df2b40464b1a43c7"
REDIRECT_URI = "https://localhost:4433/"

FRONTEND_HTML = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Casdoor Login</title>
</head>
<body style="font-family: serif;">
    <h2>Casdoor Login (Token in Cookie)</h2>
    <div id="statusText" style="margin-bottom: 5px;"></div>
    <button id="loginBtn">Login with Casdoor</button>
    <button id="infoBtn" style="display:none;">Get User Info</button>
    <pre id="output" style="font-family: monospace; font-size: 14px; margin-top: 15px;"></pre>

    <script>
        const loginBtn = document.getElementById('loginBtn');
        const infoBtn = document.getElementById('infoBtn');
        const statusText = document.getElementById('statusText');
        const output = document.getElementById('output');

        function setLoggedInUI() {{
            statusText.innerText = "Already logged in!";
            infoBtn.style.display = 'inline-block';
        }}

        loginBtn.onclick = () => {{
            window.location.href = `{CASDOOR_URL}/login/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri=${{encodeURIComponent('{REDIRECT_URI}')}}&scope=openid profile email`;
        }};

        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');

        if (code) {{
            fetch('/login', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ code: code }})
            }})
            .then(res => res.json())
            .then(data => {{
                if(data.access_token) {{
                    document.cookie = `token=${{data.access_token}}; path=/; secure`;
                    window.history.replaceState({{}}, document.title, "/"); 
                    setLoggedInUI();
                }}
            }});
        }} else if (document.cookie.includes('token=')) {{
            setLoggedInUI();
        }}

        infoBtn.onclick = () => {{
            const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
            fetch('/user-info', {{
                headers: {{ 'Authorization': `Bearer ${{token}}` }}
            }})
            .then(async res => {{
                if (res.status === 401) {{
                    output.innerText = "401 Unauthorized: Token is invalid.";
                }} else {{
                    output.innerText = await res.text();
                }}
            }});
        }};
    </script>
</body>
</html>
"""

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path.startswith('/?code='):
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(FRONTEND_HTML.encode('utf-8'))
            
        elif self.path == '/user-info':
            auth = self.headers.get('Authorization')
            if not auth:
                self.send_response(401)
                self.end_headers()
                return
            
            token = auth.split(' ')[1]
            try:
                resp = requests.get(f"{CASDOOR_URL}/api/userinfo", headers={'Authorization': f'Bearer {token}'})
                
                if resp.status_code != 200 or "error" in resp.text:
                    self.send_response(401)
                    self.end_headers()
                    return

                data = resp.json()
                result = {
                    "userId": data.get("sub"),
                    "username": data.get("name")
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result, indent=2).encode('utf-8'))
            except:
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/login':
            content_length = int(self.headers['Content-Length'])
            code = json.loads(self.rfile.read(content_length)).get('code')
            
            payload = {
                'grant_type': 'authorization_code',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'code': code,
                'redirect_uri': REDIRECT_URI
            }
            resp = requests.post(f"{CASDOOR_URL}/api/login/oauth/access_token", data=payload)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(resp.content)
        else:
            self.send_response(404)
            self.end_headers()

port = 4433 
httpd = HTTPServer(('localhost', port), SimpleHTTPRequestHandler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile="localhost.pem", keyfile="localhost-key.pem")
httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

print(f"Server: https://localhost:{port}/")
httpd.serve_forever()