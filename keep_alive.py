"""
keep_alive.py - 7/24 Hosting icin Flask Web Sunucusu
Botu UptimeRobot gibi servislerle ayakta tutmak icin
web sunucusu acar. Bot crash olursa Replit otomatik yeniden baslatir.

Kullanim:
1. main.py icinde bu modulu import et:
   from keep_alive import keep_alive
   keep_alive()
2. UptimeRobot'a Replit URL'sini ekle (5 dakikada bir ping)
"""
from threading import Thread
from flask import Flask
import logging

# Flask loglarini sustur
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('')


@app.route('/')
def home():
    """Ana sayfa - basit bir mesaj dondurur."""
    return (
        "<html><body style='font-family: monospace; background: #2C2F33; color: #57F287; padding: 20px;'>"
        "<h1>🧟‍♂️ TLOU Anadolu Bot</h1>"
        "<p>Status: <strong style='color:#57F287'>AKTIF</strong></p>"
        "<p>Bot 7/24 calisiyor.</p>"
        "<hr>"
        "<small>Bot Dev: Replit + UptimeRobot</small>"
        "</body></html>"
    )


@app.route('/health')
def health():
    """Saglik kontrolu."""
    return '{"status": "ok"}', 200


@app.route('/ping')
def ping():
    """UptimeRobot icin ping endpoint."""
    return 'pong', 200


def run():
    """Flask sunucusunu baslat."""
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    """Flask sunucusunu ayri thread'de baslatir.
    main.py icinde cagrilir.
    """
    t = Thread(target=run)
    t.daemon = True  # Ana thread kapandiginda bu da kapansin
    t.start()
    print("[keep_alive] Web sunucusu baslatildi (port 8080)")
