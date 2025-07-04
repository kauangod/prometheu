import RPi.GPIO as GPIO
import time
from luma.core.interface.serial import spi
from luma.lcd.device import ili9341
from PIL import Image, ImageDraw, ImageFont
from picamera2 import Picamera2
from pyzbar.pyzbar import decode
from pyln.client import LightningRpc
from bitcoinrpc.authproxy import AuthServiceProxy
import os
from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, WifEncoder, CoinsConf, WifPubKeyModes
from bip_utils import Bip44Changes
from bip_utils import Bip39MnemonicValidator


actual = 0

def gerar_mnemonico(num_palavras=12):
    if num_palavras not in (12, 24):
        raise ValueError("Número de palavras deve ser 12 ou 24")
    mnemonico = Bip39MnemonicGenerator().FromWordsNumber(
        Bip39WordsNum.WORDS_NUM_12 if num_palavras == 12 else Bip39WordsNum.WORDS_NUM_24
    )
    return mnemonico

# Constantes
NUM_PALAVRAS_OBJETIVO = 12  # ou 24 se quiser um mnemonic mais forte

def generate_mnemonics():
    return Bip39MnemonicGenerator().FromWordsNumber(24)

def generate_seed(mnemonics):
    return Bip39SeedGenerator(mnemonics).Generate()


def generate_wallet(seed_bytes):
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
    bip44_change_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
    bip44_addr_ctx = bip44_change_ctx.AddressIndex(0)
    return bip44_addr_ctx.PrivateKey().Raw().ToBytes()

# Soma o saldo total dos outputs de um node
def saldo_total(node_funds):
    return sum([out['amount_msat'] for out in node_funds['outputs']]) / 1000  # em satoshis

# Carregar a lista BIP-39 direto do arquivo (ou hardcoded se preferir)
def carregar_lista_bip39():
    with open("bip39_english.txt", "r") as f:
        return [linha.strip() for linha in f.readlines()]

bip39_words_list = carregar_lista_bip39()

def palavra_valida_bip39(palavra):
    return palavra.strip().lower() in bip39_words_list

def salvar_palavras_arquivo(vetor):
    with open("palavras_digitadas.txt", "w") as f:
        for p in vetor:
            f.write(p + "\n")

# ====== GPIO - Teclado ======
ROW_PINS = [4, 17, 27, 19]     # Linhas
COL_PINS = [23, 5, 6, 12]      # Colunas

KEYPAD = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D']
]

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for row in ROW_PINS:
    GPIO.setup(row, GPIO.IN, pull_up_down=GPIO.PUD_UP)

for col in COL_PINS:
    GPIO.setup(col, GPIO.OUT)
    GPIO.output(col, GPIO.HIGH)

def ler_tecla():
    for col_index, col_pin in enumerate(COL_PINS):
        GPIO.output(col_pin, GPIO.LOW)
        for row_index, row_pin in enumerate(ROW_PINS):
            if GPIO.input(row_pin) == GPIO.LOW:
                tecla = KEYPAD[row_index][col_index]
                while GPIO.input(row_pin) == GPIO.LOW:
                    time.sleep(0.05)
                GPIO.output(col_pin, GPIO.HIGH)
                if(tecla == '*' or tecla == '#'):
                    return (tecla)
               
                else:
                    if(tecla == 'C'):
                        global flag_regpalavra
                        flag_regpalavra = 1
                        print("flag = 1")
                        return 'C'
                    return convert_ascii(tecla)
        GPIO.output(col_pin, GPIO.HIGH)
    return None

def convert_ascii(tecla):
    global actual 
    actual = int(actual)
    
    if (actual == 0):
        actual = int(tecla)
        print(actual)
    elif (tecla == 'D'):
        print(actual)
        return actual 
    elif tecla != 'D' and actual > 0:
        actual = actual*10 +int(tecla)
        print(actual)
        return ler_tecla() 

# ====== Tela - luma.lcd ====== por alguma razao o tamanho da tela esta dando errado,, nem ideia o porque
serial = spi(port=0, device=0, gpio_DC=24, gpio_RST=25)
device = ili9341(serial, width=320, height=240, rotate=0)

def cadastrar_palavras(palavra): 
    with Image.new("RGB", device.size, "black") as img: 
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 80, 220, 130), outline="white", width=2)
        draw.text((15, 85), f"Palavra: {(palavra)}", fill="white") 
        device.display(img)

def desenhar_tela_login(login, senha, fase):
    with Image.new("RGB", device.size, "black") as img:
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 80, 220, 130), outline="white", width=2)
        if fase == "senha":
            draw.text((15, 85), f"Senha: {'*'*len(senha)}", fill="white")
        else:
            draw.text((15, 85), "Senha:", fill="gray")

        device.display(img)

def desenhar_logado():
    with Image.new("RGB", device.size, "black") as img:
        draw = ImageDraw.Draw(img)
        draw.rectangle((40, 100, 200, 140), fill="black")
        draw.text((60, 80), "Aperte * para gerar qr code", fill="white")
        draw.rectangle([(55,75), (185, 95 )], outline = "white")  
        draw.rectangle([(55,115), (185, 135 )], outline = "white") 
        draw.text((60, 120), "Aperte # para ler qr code", fill="white")
        device.display(img)


def desenhar_ler():
    with Image.new("RGB", device.size, "black") as img:
        draw = ImageDraw.Draw(img)
        draw.rectangle((40, 100, 200, 140), fill="black")
        draw.text((60, 80), "Aproxime a camera do QR code", fill="white")
        draw.rectangle([(55,75), (185, 115)], outline = "white")   
        device.display(img)


def camera():
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
            time.sleep(0.2)  # Evita rodar freneticamente
    except KeyboardInterrupt:
        print("🛑 Finalizado pelo usuário.")

    picam2.stop()

# ====== main ======
# ====== main ======
if __name__ == "__main__":
    hashtag = 0
    palavra = ""
    vetor_palavras = []
    flag_regpalavra = 0
    estado = -1
    actual = 0
    login = ""
    senha = ""
    fase = "senha"

    # --- Verificar se já tem 12 palavras salvas ---
    if os.path.exists("palavras_digitadas.txt"):
        with open("palavras_digitadas.txt", "r") as f:
            linhas = f.readlines()
            for linha in linhas:
                palavra_lida = linha.strip().lower()
                if palavra_valida_bip39(palavra_lida):
                    vetor_palavras.append(palavra_lida)

    if len(vetor_palavras) >= NUM_PALAVRAS_OBJETIVO:
        print("✅ 12 palavras BIP-39 já estavam salvas:")
        print(" ".join(vetor_palavras[:NUM_PALAVRAS_OBJETIVO]))
        estado = 0  # Pula direto para gerar chave
    else:
        print(f"🔧 {len(vetor_palavras)} palavras válidas encontradas. Digite mais até {NUM_PALAVRAS_OBJETIVO}.")

    try:
        while estado == -1:
            cadastrar_palavras(palavra)
            if hashtag == 0:
                tecla = ler_tecla()
            else:
                tecla = str(input())

            if tecla:
                if flag_regpalavra == 1 or tecla == ';':
                    palavra = palavra.strip().lower()
                    if palavra_valida_bip39(palavra):
                        vetor_palavras.append(palavra)
                        print("✅ Palavra registrada:", palavra)
                        with open("palavras_digitadas.txt", "a") as f:
                            f.write(palavra + "\n")
                    else:
                        print("❌ Palavra inválida BIP-39:", palavra)
                    palavra = ""
                    flag_regpalavra = 0

                elif tecla == "*":
                    if len(vetor_palavras) >= NUM_PALAVRAS_OBJETIVO:
                        estado = 0
                        break
                    else:
                        print(f"⛔ Faltam {NUM_PALAVRAS_OBJETIVO - len(vetor_palavras)} palavras BIP-39 válidas")

                elif tecla == "#":
                    hashtag = 1
                    print("Teclado ativado")

                elif tecla == "^":
                    mnemonico = Bip39MnemonicGenerator().FromWordsNumber(NUM_PALAVRAS_OBJETIVO)
                    print("Mnemônico gerado automaticamente:\n", mnemonico)
                    vetor_palavras = str(mnemonico).split()
                    salvar_palavras_arquivo(vetor_palavras)
                    estado = 0  # Já tem palavras suficientes, pula para geração
                    break

                elif hashtag == 0:
                    # Aqui tecla pode ser string ou número dependendo do ler_tecla, adapte se necessário
                    # Se for int, converte para char
                    if isinstance(tecla, int):
                        palavra += chr(tecla)
                    else:
                        palavra += tecla

                elif hashtag == 1:
                    palavra += tecla

        # Usar apenas as primeiras 12 palavras válidas
        vetor_palavras = vetor_palavras[:NUM_PALAVRAS_OBJETIVO]

        # Mostrar mnemonic
        mnemonics = ' '.join(vetor_palavras)
        print("\n🧠 Mnemonic final:")
        print(mnemonics)

        # Validar mnemonic
        try:
            Bip39MnemonicValidator().Validate(mnemonics)
        except Exception as e:
            print("❌ Mnemonic final inválido:", e)
            exit(1)

        # Gerar seed e chaves
        seed = generate_seed(mnemonics)
        print("🧬 Seed (hex):", seed.hex())

        priv_key = generate_wallet(seed)
        print("🔑 Private key (hex):", priv_key.hex())

        net_ver = CoinsConf.BitcoinTestNet.ParamByKey("wif_net_ver")
        wif_key = WifEncoder.Encode(priv_key, net_ver, WifPubKeyModes.COMPRESSED)
        print("🔐 WIF key:", wif_key)

        time.sleep(5)


        desenhar_tela_login(login, senha, fase)
        while estado == 0:
            if hashtag == 0:
                tecla = ler_tecla()
            else:
                tecla = str(input())

            if tecla:
                if tecla == "*":
                    if fase == "senha" and senha == "1234":
                        estado = 1
                        break
                    elif fase == "senha" and senha != "1234":
                        senha = ""
                        fase = "senha"
                elif tecla == "#":
                    hashtag = 1

                elif hashtag == 0:
                    if fase == "senha":
                        senha += chr(tecla)
                    actual = int(0)

                elif hashtag == 1:
                    if fase == "senha":
                        senha += tecla

                desenhar_tela_login(login, senha, fase)

        while estado == 1:
            desenhar_logado()
            tecla = ler_tecla()
            if tecla:
                if tecla == "*":
                    estado = 3
                    break
                elif tecla == "#":
                    estado = 2
                    break
            desenhar_logado()

        print(estado)

        while estado == 2:
            desenhar_ler()
            camera()

        # Tela final
        time.sleep(5)

    finally:
        GPIO.cleanup()
 
