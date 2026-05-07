import asyncio
import ssl
import json
import websockets
import aiohttp

from aiohttp import web
import message_pb2

CASDOOR_URL = "http://localhost:8000"
CLIENT_ID = "7a300b59b0a8c24bba9e"
CLIENT_SECRET = "3e8b1ee3545fed5c0bf475d3df2b40464b1a43c7"
REDIRECT_URI = "https://localhost:4433/"

clients = {}

FRONTEND_HTML = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Casdoor Login</title>
    <script src="https://cdn.jsdelivr.net/npm/protobufjs@7.2.5/dist/protobuf.min.js"></script>
</head>
<body style="font-family: serif;">

<h1>Casdoor Login (Token in Cookie)</h1>
<div id="statusText" style="margin-bottom: 5px;"></div>
<button id="loginBtn">Login with Casdoor</button>
<button id="infoBtn">Get User Info</button>
<pre id="output" style="font-family: monospace; font-size: 14px; margin-top: 15px;"></pre>

<h2>Cryptocurrency Updates</h2>
<div style="margin-bottom: 10px;">
    <b>Select coins to track:</b><br>
    <label><input type="checkbox" class="coin-cb" value="btcusdt" checked> BTC</label>
    <label><input type="checkbox" class="coin-cb" value="ethusdt" checked> ETH</label>
    <label><input type="checkbox" class="coin-cb" value="xrpusdt" checked> XRP</label>
    <label><input type="checkbox" class="coin-cb" value="dogeusdt"> DOGE</label>
</div>
<button id="subscribeBtn">Subscribe to Updates</button>
<div id="prices" style="margin-top:20px;"></div>

<script>
const pbRoot = protobuf.Root.fromJSON({{
  nested: {{
    PriceUpdate: {{
      fields: {{
        symbol: {{ type: "string", id: 1 }},
        price: {{ type: "string", id: 2 }}
      }}
    }}
  }}
}});
const PriceUpdateMsg = pbRoot.lookupType("PriceUpdate");

const loginBtn = document.getElementById('loginBtn');
const infoBtn = document.getElementById('infoBtn');
const subscribeBtn = document.getElementById('subscribeBtn');
const statusText = document.getElementById('statusText');
const output = document.getElementById('output');
const pricesDiv = document.getElementById('prices');

let socket = null;
const previousPrices = {{}};

function setLoggedInUI() {{
    statusText.innerText = "Already logged in!";
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
    if (!token) return alert("Error: Please login first!");

    fetch('/user-info', {{
        headers: {{ 'Authorization': `Bearer ${{token}}` }}
    }})
    .then(async res => {{
        output.innerText = res.status === 401 ? "401 Unauthorized: Token is invalid." : await res.text();
    }});
}};

subscribeBtn.onclick = () => {{
    const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
    if (!token) return alert("Error: Please login first!");

    const selectedSymbols = Array.from(document.querySelectorAll('.coin-cb:checked')).map(cb => cb.value);
    if (selectedSymbols.length === 0) return alert("Please select at least one coin!");

    if (socket) {{
        socket.close();
        pricesDiv.innerHTML = "";
    }}

    socket = new WebSocket(`wss://localhost:4433/ws?token=${{token}}`);
    socket.binaryType = "arraybuffer";

    socket.onopen = () => {{
        console.log("Connected to WebSocket");
        statusText.innerText = "Connected to WebSocket.";
        socket.send(JSON.stringify({{ symbols: selectedSymbols }}));
    }};

    socket.onmessage = (event) => {{
        const decodedMessage = PriceUpdateMsg.decode(new Uint8Array(event.data));
        const data = PriceUpdateMsg.toObject(decodedMessage, {{ defaults: true }});
        
        const symbol = data.symbol;
        const currentPrice = parseFloat(data.price);
        const priceText = currentPrice.toFixed(2); 
        const timeString = new Date().toLocaleTimeString('en-US', {{ hour12: false }});

        let div = document.getElementById(`coin-${{symbol}}`);
        if (!div) {{
            div = document.createElement('div');
            div.id = `coin-${{symbol}}`;
            div.style.cssText = "padding: 10px; margin: 5px; border: 1px solid #ddd; border-radius: 5px;";
            pricesDiv.appendChild(div);
        }}

        if (previousPrices[symbol] !== undefined) {{
            div.style.background = currentPrice > previousPrices[symbol] ? "#e8f5e8" : (currentPrice < previousPrices[symbol] ? "#f8e8e8" : "#ffffff");
        }} else {{
            div.style.background = "#ffffff";
        }}

        previousPrices[symbol] = currentPrice;
        div.innerHTML = `<b>${{symbol}}</b>: $${{priceText}} <span style="font-size: 12px; color: gray;">(${{timeString}})</span>`;
    }};
}};
</script>
</body>
</html>
"""

async def validate_token(token):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{CASDOOR_URL}/api/userinfo",
                headers={"Authorization": f"Bearer {token}"}
            ) as resp:
                return resp.status == 200
    except Exception:
        return False

async def binance_listener(symbol):
    url = f"wss://stream.binance.com/ws/{symbol}@trade"

    while True:
        try:
            print(f"Connecting to Binance: {url}")
            async with websockets.connect(url) as ws:
                print(f"Connected to Binance for {symbol}")

                async for message in ws:
                    data = json.loads(message)
                    
                    protobuf_msg = message_pb2.PriceUpdate(
                        symbol=symbol.replace("usdt", "").upper(),
                        price=str(data["p"])
                    )
                    protobuf_binary = protobuf_msg.SerializeToString()

                    if symbol in clients:
                        stale_clients = set()
                        for client in clients[symbol]:
                            try:
                                await client.send_bytes(protobuf_binary)
                            except Exception as e:
                                print("SEND ERROR:", e)
                                stale_clients.add(client)

                        if stale_clients:
                            clients[symbol] -= stale_clients

        except Exception as e:
            print(f"BINANCE ERROR ({symbol}):", e)
            await asyncio.sleep(5)

async def websocket_handler(request):
    token = request.query.get("token")

    if not token or not await validate_token(token):
        return web.Response(status=401, text="Unauthorized")

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            
            for symbol in data.get("symbols", []):
                symbol = symbol.lower().strip()
                print("Client subscribed to:", symbol)
                
                if symbol not in clients:
                    clients[symbol] = set()
                clients[symbol].add(ws)

    return ws

async def index(request):
    return web.Response(text=FRONTEND_HTML, content_type='text/html')

async def login(request):
    data = await request.json()
    payload = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': data.get("code"),
        'redirect_uri': REDIRECT_URI
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{CASDOOR_URL}/api/login/oauth/access_token", data=payload) as resp:
            text_response = await resp.text()
            return web.Response(text=text_response, content_type='application/json')

async def user_info(request):
    auth = request.headers.get('Authorization')
    if not auth:
        return web.Response(status=401)
    
    token = auth.split(' ')[1]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{CASDOOR_URL}/api/userinfo",
                headers={'Authorization': f'Bearer {token}'}
            ) as resp:
                
                if resp.status != 200:
                    return web.Response(status=401)

                data = await resp.json()
                result = {
                    "userId": data.get("sub"),
                    "username": data.get("name")
                }
                
                return web.Response(
                    text=json.dumps(result, indent=2),
                    content_type='application/json'
                )
    except Exception:
        return web.Response(status=500)

async def main():
    app = web.Application()

    app.router.add_get('/', index)
    app.router.add_post('/login', login)
    app.router.add_get('/user-info', user_info)
    app.router.add_get('/ws', websocket_handler)

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain('localhost.pem', 'localhost-key.pem')
    ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
    ssl_context.set_ciphers('RSA')

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, 'localhost', 4433, ssl_context=ssl_context)
    await site.start()

    print("HTTPS/WSS server started")
    print("https://localhost:4433")


    for coin in ["btcusdt", "ethusdt", "xrpusdt", "dogeusdt"]:
        asyncio.create_task(binance_listener(coin))
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())