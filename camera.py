from picamera2 import Picamera2
import time
import os

# Define o caminho para salvar a imagem
home_dir = os.path.expanduser("~")
save_dir = os.path.join(home_dir, "Desktop", "prometheu")
os.makedirs(save_dir, exist_ok=True)  # Cria o diretório se não existir

# Inicializa a câmera
picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration())

picam2.start()
time.sleep(2)  # Aguarda a câmera ajustar exposição/foco

# Captura a imagem
image_path = os.path.join(save_dir, "new_image.jpg")
picam2.capture_file(image_path)

picam2.stop()
print(f"Imagem salva em: {image_path}")

