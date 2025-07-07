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
import cv2
import json
from dotenv import load_dotenv

load_dotenv()

def reais_para_btc(valor_em_reais_str):
    """
    Converte um valor em reais no formato string '12.50'
    para o valor correspondente em BTC, usando a variável global `btc_em_reais`.
    """
    
    VALOR_BTC = float(585693.72)
    try:
        valor_em_reais = float(valor_em_reais_str.replace(",", "."))  # Suporta ',' ou '.'
        btc = valor_em_reais / VALOR_BTC
        return btc
    except ValueError:
        print("Erro: valor inválido.")
        return None

actual = 0

def gerar_mnemonico(num_palavras=24):
    if num_palavras not in (12, 24):
        raise ValueError("Número de palavras deve ser 12 ou 24")
    mnemonico = Bip39MnemonicGenerator().FromWordsNumber(
        Bip39WordsNum.WORDS_NUM_12 if num_palavras == 24 else Bip39WordsNum.WORDS_NUM_24
    )
    return mnemonico

# Constantes
NUM_PALAVRAS_OBJETIVO = 24  # ou 24 se quiser um mnemonic mais forte

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
    with open("mnemonics.txt", "w") as f:
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
device = ili9341(serial, width=240, height=240, rotate=1)

def cadastrar_palavras(palavra): 
    with Image.new("RGB", device.size, "black") as img: 
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 80, 220, 130), outline="white", width=2)
        draw.text((15, 85), f"Palavra: {(palavra)}", fill="white") 
        device.display(img.rotate(270))

def selecionar_valor(palavra): 
    with Image.new("RGB", device.size, "black") as img: 
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 80, 220, 130), outline="white", width=2)
        draw.text((15, 85), f"Valor a ser transferido: R${(palavra)}", fill="white") 
        device.display(img.rotate(270))

def tela_boot(): 
    with Image.new("RGB", device.size, "black") as img: 
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 80, 220, 130), outline="white", width=2)
        draw.text((15, 85), f"Boot", fill="white") 
        device.display(img.rotate(270))

def desenhar_tela_login(login, senha, fase):
    with Image.new("RGB", device.size, "black") as img:
        draw = ImageDraw.Draw(img)
        draw.rectangle((10, 80, 220, 130), outline="white", width=2)
        if fase == "senha":
            draw.text((15, 85), f"Senha: {'*'*len(senha)}", fill="white")
        else:
            draw.text((15, 85), "Senha:", fill="gray")

        device.display(img.rotate(270))

def desenhar_logado():
    with Image.new("RGB", device.size, "black") as img:
        draw = ImageDraw.Draw(img)
        draw.rectangle((40, 100, 200, 140), fill="black")
        draw.text((60, 80), "Aperte * para gerar qr code", fill="white")
        draw.rectangle([(55,75), (185, 95 )], outline = "white")  
        draw.rectangle([(55,115), (185, 135 )], outline = "white") 
        draw.text((60, 120), "Aperte # para ler qr code", fill="white")
        device.display(img.rotate(270))


def desenhar_ler():
    with Image.new("RGB", device.size, "black") as img:
        draw = ImageDraw.Draw(img)
        draw.rectangle((40, 100, 200, 140), fill="black")
        draw.text((60, 80), "Aproxime a camera do QR code", fill="white")
        draw.rectangle([(55,75), (185, 115)], outline = "white")   
        device.display(img.rotate(270))


def camera():
    picam2 = Picamera2()
    picam2.configure(picam2.create_preview_configuration(main={"format": "RGB888", "size": (960, 582)}))
    picam2.start()
    time.sleep(2)

    print("📷 Aguardando QR Code... Ctrl+C para sair")

    try:
        while True:
            frame = picam2.capture_array()
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            decoded_objects = decode(gray)
            if decoded_objects:
                for obj in decoded_objects:
                    data = obj.data.decode("utf-8")
                    #retorno = json.loads(data)
                    #print(retorno)
                    #print(type(retorno))
                    return data

            time.sleep(0.1)
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
    tela_boot()
    # --- Verificar se já tem 12 palavras salvas ---
    if os.path.exists("mnemonics.txt"):
        with open("mnemonics.txt", "r") as f:
            linhas = f.readlines()
            for linha in linhas:
                palavra_lida = linha.strip().lower()
                if palavra_valida_bip39(palavra_lida):
                    vetor_palavras.append(palavra_lida)

    if len(vetor_palavras) >= NUM_PALAVRAS_OBJETIVO:
        print("✅ 24 palavras BIP-39 já estavam salvas:")
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
                        with open("mnemonics.txt", "a") as f:
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

        # Usar apenas as primeiras 24 palavras válidas
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
                    print("Teclado ativado")

                elif hashtag == 0:
                    if fase == "senha":
                        senha += chr(tecla)
                    actual = int(0)

                elif hashtag == 1:
                    if fase == "senha":
                        senha += tecla

                desenhar_tela_login(login, senha, fase)


        # --- CONFIGURAÇÕES DE AMBIENTE ---
        NODE1_RPC_PATH = os.getenv("LIGHTNING_RPC_PATH_PI")

        # Dados do Prometheu PC (Node 2)
        NODE2_IP = os.getenv("NODE2_IP")
        NODE2_PORT = int(os.getenv("NODE2_PORT"))

        # Dados de conexão do Bitcoin Core (Prometheu PC)
        rpc_user = os.getenv("BITCOIN_RPC_USER")
        rpc_password = os.getenv("BITCOIN_RPC_PASSWORD")
        rpc_host = os.getenv("NODE2_IP")
        rpc_port = int(os.getenv("BITCOIN_RPC_PORT"))
        wallet_name = "prometheu_wallet"

        # --- INICIALIZAÇÃO DAS CONEXÕES ---
        rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}/wallet/{wallet_name}")
        rpc_node1 = LightningRpc(NODE1_RPC_PATH)
        
        # 4. Cria wallet no Bitcoin Core (se não existir)
        try:
            rpc_connection.createwallet("prometheu_wallet", False, False, "", False, False, True)
            rpc_connection.generatetoaddress(3, rpc_connection.getnewaddress())
        except Exception as e:
            print(f"Wallet já existe ou erro ao criar: {e}")

        # 5. Checa se a wallet existe ou já está carregada e importa chave privada
        try:
            rpc_connection.loadwallet("prometheu_wallet")
        except Exception as e:
            print(f"Erro ao carregar wallet: {e}")
        finally:
            print(f"Saldo da wallet on-chain: {rpc_connection.getbalance()}")
            rpc_connection.importprivkey(wif_key)
            print("---------------------------")
            print(f"Saldo da wallet on-chain após importação da chave privada: {rpc_connection.getbalance()}")

            # 6. Pega endereço Lightning on-chain
            prometheu_dir_pi = os.getenv("PROMETHEU_DIR_PI")
            with open(f'{prometheu_dir_pi}/lightning_address.txt', 'r') as f:
                lightning_address = f.read().strip()
                if not lightning_address:
                    lightning_address = rpc_node1.newaddr()["bech32"]
                    with open(f'{prometheu_dir_pi}/lightning_address.txt', 'w') as f:
                        f.write(lightning_address)

            print("---------------------------")
            print(f"Endereço on-chain da Lightning wallet: {lightning_address}")
            node1_funds_temp = rpc_node1.listfunds()
            print(f"Saldo total Node 1: {saldo_total(node1_funds_temp)} satoshis")
            rpc_connection.generatetoaddress(10, rpc_connection.getnewaddress())

        palavra = ""
        selecionar_valor(palavra)
        while estado == 1:
            if hashtag == 0:
                tecla = ler_tecla()
            else:
                tecla = str(input())

            if tecla:
                if tecla == "*" and palavra != "":
                    estado = 2
                    break
                elif tecla == "#":
                    hashtag = 1
                    print("Teclado ativado")

                elif hashtag == 0:
                    palavra += chr(tecla)
                    actual = int(0)

                elif hashtag == 1:
                    palavra += tecla

                selecionar_valor(palavra)

        print(palavra)
        valor_em_btc = reais_para_btc(palavra)
        print(valor_em_btc)
        # 7. Envia 1 BTC da wallet para a carteira Lightning
        txid = rpc_connection.sendtoaddress(lightning_address, float(1)) # Colocar aqui o valor que deseja enviar para a Lightning wallet, escolha do usuário (Valor em BTC).
        print("---------------------------")
        print(f"Transação enviada para Lightning. TXID: {txid}")
       
        # 8. Minerar blocos para confirmar no regtest (gera 3 blocos)
        print("---------------------------")
        print("Minerando blocos para confirmar...")
        rpc_connection.generatetoaddress(3, rpc_connection.getnewaddress())
        print("---------------------------")
        print("Blocos minerados.")

        # 9. Verifica saldo após mineração
        print("---------------------------")
        print(f"Saldo da wallet on-chain: {rpc_connection.getbalance()}")
        node1_funds_temp = rpc_node1.listfunds()
        print(f"Saldo total Node 1: {saldo_total(node1_funds_temp)} satoshis") # Se quiserem colocar em reais, façam a conversão.
       
        while estado == 2:
            desenhar_logado()
            tecla = ler_tecla()
            if tecla:
                if tecla == "*":
                    estado = 2
                    break
                elif tecla == "#":
                    estado = 4
                    break
            desenhar_logado()

        print(estado)
        
        qr_code = ""
        while estado == 4 and qr_code == "":
            desenhar_ler()
            qr_code = camera()
            
        
        infos_node2 = json.loads(qr_code)  # Desempacotar o valor do qrcode gerado no node 2, saída esperada: {"invoice": {"bolt11": "...", "destination": "..."}, "node": {"lightning_address": "bcrt1...", "node_id": "..."}}
        
        
        
        with open("infos_node.json", "w", encoding="utf-8") as f:
            json.dump(infos_node2, f, indent=4, ensure_ascii=False)
            f.write("\n")  # Garante newline no final do arquivo

        with open("infos_node.json", "r", encoding="utf-8") as f:
            infos_node2 = json.load(f)


        bolt11_invoice = infos_node2["invoice"]["bolt11"]
        node2_address = infos_node2["node"]["lightning_address"]
        node2_id = infos_node2["node"]["node_id"]
        print("---------------------------")
        print(f"Invoice node PC (BOLT11) recebida: {bolt11_invoice}")
        
        
        
        # 11. Conecta-se ao Prometheu PC (Node 2) e abre canal de pagamento
        # Use as variáveis de configuração para conectar
        rpc_node1.connect(node2_id, NODE2_IP, NODE2_PORT)
        funding_address = rpc_node1.fundchannel(node2_id, '1000000sat')  # 100.000 msat = 0.001 BTC
        print("---------------------------")
        print(f"Canal aberto: {funding_address}")

        # 12. Confirma o canal minerando 6 blocos
        address = "bcrt1qas5pjsm9rkl02r5t9zellxfmt9yrjf4wypswes"
        rpc_connection.generatetoaddress(6, address)

        # 13. Realiza pagamento via pay (aqui é o pagamento feito pelo PI para o Prometheu PC (Node 2))
        pay_result = rpc_node1.pay(bolt11_invoice)
        print("---------------------------")
        print(f"Pagamento enviado: {pay_result}")

        # 14. Obter id do canal utilizado para o pagamento (último canal)
        node1_funds = rpc_node1.listfunds()
        channel_id = None
        if node1_funds["channels"]:
            ch = node1_funds["channels"][-1]
            channel_id = ch["channel_id"] if "channel_id" in ch else ch.get("short_channel_id")
            print(f"Canal utilizado: {ch}")
        if not channel_id:
            print("Canal não encontrado para fechamento!")
        else:
            # 15. Espera até o canal estar pronto para ser fechado (short_channel_id disponível e estado CHANNELD_NORMAL)
            max_wait = 60  # segundos
            waited = 0
            while ("short_channel_id" not in ch or ch["state"] != "CHANNELD_NORMAL") and waited < max_wait:
                print(f"Aguardando canal lockin... Estado atual: {ch['state']}")
                time.sleep(2)
                waited += 2
                node1_funds = rpc_node1.listfunds()
                if node1_funds["channels"]:
                    ch = node1_funds["channels"][-1]
            if "short_channel_id" not in ch or ch["state"] != "CHANNELD_NORMAL":
                raise Exception("Canal não ficou pronto para fechamento (lockin) após tempo limite!")
            short_channel_id = ch["short_channel_id"]
            close_result = rpc_node1.close(short_channel_id, 0, destination=node2_address)
            print(f"Resultado do fechamento do canal (com short_channel_id): {close_result}")

        # 16. Printar saldo total do node (Prometheu PI)
        node1_total = saldo_total(rpc_node1.listfunds())
        print(f"Saldo total Node PI: {node1_total} satoshis")
        # Tela final
        time.sleep(5)

    finally:
        GPIO.cleanup()
