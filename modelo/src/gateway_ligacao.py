#!/usr/bin/env python3
"""
Gateway de notificação — roda no NOTEBOOK.
O ESP32 detecta "socorro" na borda e imprime na serial; este script escuta e faz
a LIGAÇÃO via Twilio (do PC, onde o HTTPS funciona sem os limites do ESP).

Arquitetura: [ESP32 = edge/detecção]  --serial-->  [notebook = gateway/notificação].

Credenciais: preencha _work/twilio.env (as mesmas do secrets.h).
Uso:  python gateway_ligacao.py
"""
import glob, time, base64, urllib.request, urllib.parse, urllib.error
from pathlib import Path
import serial

ROOT = Path(__file__).resolve().parents[2]
env = {}
for ln in (ROOT / "_work" / "twilio.env").read_text().splitlines():
    ln = ln.strip()
    if ln and not ln.startswith("#") and "=" in ln:
        k, v = ln.split("=", 1); env[k.strip()] = v.strip().strip('"')
SID, TOKEN = env["TWILIO_SID"], env["TWILIO_TOKEN"]
FROM, TO, TWIML = env["TWILIO_FROM"], env["ALERT_TO"], env["TWIML_URL"]
COOLDOWN = 30   # s entre ligações

def ligar():
    url = f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Calls.json"
    body = urllib.parse.urlencode({"To": TO, "From": FROM, "Url": TWIML}).encode()
    req = urllib.request.Request(url, data=body)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{SID}:{TOKEN}".encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"    [Twilio] HTTP {r.status} -> ligando para {TO} 📞")
    except urllib.error.HTTPError as e:
        print(f"    [Twilio] ERRO {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        print(f"    [Twilio] falha: {e}")

port = (glob.glob("/dev/cu.usbserial*") + glob.glob("/dev/cu.usbmodem*"))[0]
ser = serial.Serial(port, 115200, timeout=0.3)
print(f"Gateway ativo em {port}. Escutando 'socorro'...  (Ctrl+C para sair)")
buf = b""; last = 0.0
while True:
    buf += ser.read(256)
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        s = line.decode(errors="replace").strip()
        if "EVENT socorro" in s or "SOCORRO!" in s:
            now = time.time()
            if now - last > COOLDOWN:
                last = now
                print(f">>> SOCORRO detectado ({s}) — acionando ligação...")
                ligar()
