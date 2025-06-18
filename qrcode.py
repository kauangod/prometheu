from picamera2 import Picamera2
from pyzbar.pyzbar import decode
import time

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"format": "RGB888", "size": (1920, 1080)}))
picam2.start()
time.sleep(2)
i=0

print("📷 Aguardando QR Code... Ctrl+C para sair")

try:
    while True:
        frame = picam2.capture_array()
        decoded_objects = decode(frame)
        print("📷 Aguardando QR Code... Ctrl+C para sair")
        i=(i+1)%1000
        print(i)

        for obj in decoded_objects:
            data = obj.data.decode("utf-8")
            print(f"🔍 QR Code detectado: {data}")
        #time.sleep(0.2)  # Evita rodar freneticamente
except KeyboardInterrupt:
    print("🛑 Finalizado pelo usuário.")

picam2.stop()

