from dearpygui.dearpygui import *
import hashlib
import json
import qrcode
import numpy as np
import os
import uuid
import time
import threading

from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, WifEncoder, CoinsConf, WifPubKeyModes, Bip44Changes
from pyln.client import LightningRpc
from bitcoinrpc.authproxy import AuthServiceProxy

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
import base64

# -------------------- ESTADO GLOBAL --------------------
state = {
    "logged_in": False,
    "wrong_attempts": 0,
    "max_attempts": 3,
    "password_set": False,
    "current_screen": "initial",
    "priv_key": None
}

# -------------------- UTILITÁRIOS --------------------
def hash_sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

def derive_key_from_pin(pin: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(pin.encode()))
    return key

def encrypt_mnemonics(mnemonics: str, pin: str) -> None:
    salt = os.urandom(16)
    key = derive_key_from_pin(pin, salt)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(mnemonics.encode())
    with open("mnemonics", "wb") as f:
        f.write(salt + encrypted)

def decrypt_mnemonics(pin: str) -> str:
    with open("mnemonics", "rb") as f:
        data = f.read()
    salt = data[:16]
    encrypted = data[16:]
    key = derive_key_from_pin(pin, salt)
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted)
    return decrypted.decode()

def reais_para_milisatoshis(valor_em_reais_str):
    """
    Converte um valor em reais no formato string '12.50'
    para o valor correspondente em mili satoshis.

    Exemplo:
    - R$ 1,00 = 1000 mili satoshis
    - R$ 10,50 = 10500 mili satoshis
    - R$ 100,00 = 100000 mili satoshis

    Esta conversão é usada para compatibilidade com a Lightning Network,
    que trabalha com mili satoshis como unidade de medida.
    """

# -------------------- WALLET FUNÇÕES --------------------
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

def saldo_total(node_funds):
    return sum([out["amount_msat"] for out in node_funds["outputs"]]) / 1000

# -------------------- DEARPYGUI SETUP --------------------
create_context()
create_viewport(title="Prometheu", width=1920, height=1080)
setup_dearpygui()
set_global_font_scale(3.0)

# -------------------- TEMAS E ESTÉTICA --------------------
def create_red_button_theme():
    with theme(tag="red_button_theme"):
        with theme_component(mvButton):
            add_theme_color(mvThemeCol_Button, [200, 0, 0], category=mvThemeCat_Core)
            add_theme_color(mvThemeCol_ButtonHovered, [220, 50, 50], category=mvThemeCat_Core)
            add_theme_color(mvThemeCol_ButtonActive, [180, 0, 0], category=mvThemeCat_Core)
create_red_button_theme()

def on_close(sender, app_data, user_data):
    stop_dearpygui()

# -------------------- NAVEGAÇÃO ENTRE TELAS --------------------
def switch_window(old_tag, new_window_func, new_screen_name):
    if does_item_exist(old_tag):
        delete_item(old_tag)
    state["current_screen"] = new_screen_name
    new_window_func()

# -------------------- TELAS --------------------
def create_initial_window():
    with window(label="Prometheu - Início", width=1920, height=1080, pos=[0, 0], no_resize=True, no_collapse=True, tag="initial_window"):
        add_spacer(height=300)
        with group(horizontal=True):
            add_spacer(width=800)
            with group():
                add_button(label="Login", width=400, callback=lambda: switch_window("initial_window", create_login_window, "login"))
                add_spacer(height=60)
                add_button(label="Cadastro", width=400, callback=lambda: switch_window("initial_window", create_register_window, "register"))

def create_register_window():
    with window(label="Cadastro - Prometheu", width=1920, height=1080, pos=[0, 0], no_resize=True, no_collapse=True, on_close=on_close, tag="register_window"):
        add_spacer(height=150)
        with group(horizontal=True):
            add_spacer(width=600)
            with group():
                add_text("Cadastre uma senha segura:")
                add_input_text(password=True, tag="##new_password_input", width=700, hint="Nova senha (4 números)")
                add_spacer(height=40)

                add_checkbox(label="Inserir mnemônicos manualmente", tag="use_custom_mnemonics", callback=lambda s, a, u: configure_item("custom_mnemonics_input", show=a))
                add_input_text(tag="custom_mnemonics_input", width=700, hint="Digite seus 24 mnemônicos separados por espaço", show=False, multiline=False, tab_input=False)
                add_spacer(height=20)

                add_button(label="Criar carteira", width=700, callback=criar_carteira)
                add_spacer(height=20)

                add_button(label="Cadastrar", width=700, callback=handle_register)
                add_text("", tag="register_status", color=[255, 0, 0])
                add_spacer(height=20)
                add_button(label="Voltar", width=700, callback=lambda: switch_window("register_window", create_initial_window, "initial"))
            add_spacer(width=600)
        add_spacer(height=150)

def create_login_window():
    with window(label="Login Prometheu", width=1920, height=1080, pos=[0, 0], no_resize=True, no_collapse=True, on_close=on_close, tag="login_window"):
        add_spacer(height=300)
        with group(horizontal=True):
            add_spacer(width=600)
            with group():
                add_text("Digite a senha:")
                add_spacer(height=60)
                add_input_text(password=True, tag="##password_input", width=700, hint="Senha (4 números)")
                add_spacer(height=60)
                add_button(label="Entrar", callback=attempt_login_callback, width=700)
                add_spacer(height=20)
                add_text("", tag="login_status", color=[255, 0, 0])
                add_spacer(height=60)
                add_button(label="Voltar", width=700, callback=lambda: switch_window("login_window", create_initial_window, "initial"))
            add_spacer(width=600)
        add_spacer(height=300)

def create_main_window():
    try:
        rpc_connection = AuthServiceProxy("http://prometheu@prometheu:prometheu@127.0.0.1:8332/wallet/regtest_wallet")
        rpc_node = LightningRpc("/home/kauan/.lightning/regtest/lightning-rpc")
        node_funds = rpc_node.listfunds()
        lightning_balance = saldo_total(node_funds)
        onchain_balance = rpc_connection.getbalance()
    except Exception:
        lightning_balance = 0
        onchain_balance = 0

    with window(label="Prometheu - Painel Principal", width=1920, height=1080, pos=[0, 0], no_resize=True, no_collapse=True, on_close=on_close, tag="main_window"):
        with group():
            add_text("Bem-vindo ao Prometheu", bullet=True)
            add_separator()
            add_spacer(height=60)

            add_text("Saldo Lightning:", bullet=True)
            add_text(f"{lightning_balance:.0f} satoshis", tag="saldo_lightning")
            add_spacer(height=10)

            add_text("Saldo On-chain:", bullet=True)
            add_text(f"{onchain_balance:.8f} BTC", tag="saldo_onchain")
            add_spacer(height=10)

            add_text("", tag="saldo_status")
            add_spacer(height=40)

            add_text("Valor em Reais (R$)")
            add_input_float(tag="reais_input", width=400, step=0.5, step_fast=10.0, min_value=0.0, min_clamped=True)
            add_text("", tag="valor_status", color=[255, 0, 0])
            add_spacer(height=20)

            add_button(label="Gerar QR Code", callback=generate_and_show_qrcode, width=300)
            add_spacer(height=300)

            add_button(label="Logout", callback=logout_callback, width=300)
            bind_item_theme(last_item(), "red_button_theme")

        with child_window(tag="qr_child", width=800, height=800, border=True, pos=[900, 150]):
            pass

    threading.Thread(target=saldo_loop, daemon=True).start()

# -------------------- AÇÕES --------------------
def criar_carteira():
    use_custom = get_value("use_custom_mnemonics")
    pin = get_value("##new_password_input")

    if use_custom:
        mnemonics_input = get_value("custom_mnemonics_input") or ""
        mnemonics = mnemonics_input.strip().split()
        if len(mnemonics) != 24:
            set_value("register_status", "Você deve inserir exatamente 24 palavras mnemônicas.")
            return
        mnemonics_str = " ".join(mnemonics)
    else:
        mnemonics_str = str(generate_mnemonics())  # <-- CORREÇÃO AQUI

    try:
        seed = generate_seed(mnemonics_str)
        priv_key = generate_wallet(seed)

        net_ver = CoinsConf.BitcoinTestNet.ParamByKey("wif_net_ver")
        wif_key = WifEncoder.Encode(priv_key, net_ver, WifPubKeyModes.COMPRESSED)

        encrypt_mnemonics(mnemonics_str, pin)

        rpc_user = "prometheu@prometheu"
        rpc_password = "prometheu"
        wallet_name = "regtest_wallet"
        rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@127.0.0.1:8332/wallet/{wallet_name}")
        rpc_node = LightningRpc("/home/kauan/.lightning/regtest/lightning-rpc")

        try:
            rpc_connection.createwallet("regtest_wallet", False, False, "", False, False, True)
        except Exception:
            pass

        try:
            rpc_connection.loadwallet("regtest_wallet")
        except Exception:
            pass

        rpc_connection.importprivkey(wif_key)

        lightning_address = rpc_node.newaddr()["bech32"]
        rpc_connection.sendtoaddress(lightning_address, 1)
        rpc_connection.generatetoaddress(3, rpc_connection.getnewaddress())

        set_value("register_status", "Carteira gerada e conectada com sucesso. Você pode prosseguir.")
    except Exception as e:
        set_value("register_status", f"Erro ao criar carteira: {e}")


def load_wallet_from_mnemonics(pin):
    try:
        mnemonics_str = decrypt_mnemonics(pin)
        mnemonics_list = mnemonics_str.strip().split()
        if len(mnemonics_list) != 24:
            return None
        seed = generate_seed(mnemonics_str)
        priv_key = generate_wallet(seed)
        return priv_key
    except Exception:
        return None

def handle_register():
    pwd = get_value("##new_password_input")
    if not (pwd.isdigit() and len(pwd) == 4):
        set_value("register_status", "A senha deve conter exatamente 4 números.")
        return

    with open("pin", "w") as f:
        f.write(hash_sha256(pwd))

    state["password_set"] = True
    set_value("register_status", "")
    switch_window("register_window", create_login_window, "login")

def attempt_login_callback(sender, app_data, user_data):
    entered = get_value("##password_input")

    if not entered.isdigit() or len(entered) != 4:
        set_value("login_status", "Senha inválida. Use exatamente 4 números.")
        return

    try:
        with open("pin", "r") as f:
            stored_hash = f.read().strip()
    except FileNotFoundError:
        set_value("login_status", "Senha não cadastrada.")
        return

    if hash_sha256(entered) == stored_hash:
        priv_key = load_wallet_from_mnemonics(entered)
        if priv_key is None:
            set_value("login_status", "Erro ao carregar a carteira. Faça um novo cadastro.")
            return
        state["priv_key"] = priv_key
        state["logged_in"] = True
        state["wrong_attempts"] = 0
        switch_window("login_window", create_main_window, "main")
    else:
        state["wrong_attempts"] += 1
        tentativas_restantes = state["max_attempts"] - state["wrong_attempts"]
        if state["wrong_attempts"] >= state["max_attempts"]:
            for arquivo in ["pin", "mnemonics"]:
                if os.path.exists(arquivo):
                    os.remove(arquivo)
            state["wrong_attempts"] = 0
            set_value("login_status", "Senha incorreta 3x seguidas. Dados apagados, reinicie o cadastro.")
            switch_window("login_window", create_initial_window, "initial")
        else:
            set_value("login_status", f"Senha incorreta. Tentativas restantes: {tentativas_restantes}")

def logout_callback():
    state["logged_in"] = False
    state["wrong_attempts"] = 0
    switch_window("main_window", create_login_window, "login")

def atualizar_saldo():
    try:
        rpc_connection = AuthServiceProxy("http://prometheu@prometheu:prometheu@127.0.0.1:8332/wallet/regtest_wallet")
        rpc_node = LightningRpc("/home/kauan/.lightning/regtest/lightning-rpc")

        node_funds = rpc_node.listfunds()
        lightning_balance = saldo_total(node_funds)
        onchain_balance = rpc_connection.getbalance()

        set_value("saldo_lightning", f"{lightning_balance:.0f} satoshis")
        set_value("saldo_onchain", f"{onchain_balance:.8f} BTC")
        set_value("saldo_status", f"Última atualização: {time.strftime('%H:%M:%S')}")

    except Exception as e:
        set_value("valor_status", f"Erro ao atualizar saldo: {e}")

def saldo_loop():
    while True:
        if state["current_screen"] == "main" and state["logged_in"]:
            atualizar_saldo()
        time.sleep(10)

def check_invoice_payment(label):
    try:
        rpc_node = LightningRpc("/home/kauan/.lightning/regtest/lightning-rpc")
        while True:
            if state["current_screen"] != "main":
                break
            invoice_status = rpc_node.listinvoices(label)
            if invoice_status["invoices"]:
                status = invoice_status["invoices"][-1]["status"]
                if status == "paid":
                    set_value("valor_status", "Invoice paga! Saldo atualizado.")
                    break
                else:
                    set_value("valor_status", f"Aguardando pagamento... Status: {status}")
            else:
                set_value("valor_status", "Invoice não encontrada.")
            time.sleep(3)
    except Exception as e:
        set_value("valor_status", f"Erro ao verificar invoice: {e}")

def start_invoice_thread(label):
    thread = threading.Thread(target=check_invoice_payment, args=(label,), daemon=True)
    thread.start()

def generate_and_show_qrcode():
    reais = get_value("reais_input")
    if reais is None or reais <= 0:
        set_value("valor_status", "Informe um valor válido.")
        return
    set_value("valor_status", "")

    try:
        rpc_node = LightningRpc("/home/kauan/.lightning/regtest/lightning-rpc")
        node_info = rpc_node.getinfo()
        random_label = str(uuid.uuid4())
        invoice = rpc_node.invoice(int(reais * 1000), random_label, f"Pagamento de R${reais:.2f}")

        infos_node = {
            "invoice": invoice,
            "node": {
                "lightning_address": rpc_node.newaddr()["bech32"],
                "node_id": node_info["id"]
            }
        }

        with open("infos_node.json", "w") as f:
            json.dump(infos_node, f, indent=4)

        start_invoice_thread(random_label)

    except Exception as e:
        set_value("valor_status", f"Erro ao gerar invoice: {e}")
        return

    with open("infos_node.json") as f:
        tx = json.load(f)

    json_text = json.dumps(tx)

    qr = qrcode.make(json_text).convert("RGBA").resize((780, 780))
    img_data = np.array(qr, dtype=np.uint8).astype(np.float32) / 255.0
    img_data_flat = img_data.flatten()

    if does_item_exist("qr_image"):
        delete_item("qr_image")
    if does_item_exist("qr_texture"):
        delete_item("qr_texture")

    with texture_registry(show=False):
        add_static_texture(780, 780, img_data_flat, tag="qr_texture")

    add_image("qr_texture", tag="qr_image", width=780, height=780, parent="qr_child")

# -------------------- EXECUÇÃO --------------------
create_initial_window()
state["current_screen"] = "initial"
show_viewport()
start_dearpygui()
destroy_context()
