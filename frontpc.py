from dearpygui.dearpygui import *
import json
import qrcode
import numpy as np
import zlib
import base64

state = {
    "logged_in": False,
    "wrong_attempts": 0,
    "max_attempts": 3,
    "password": "1234",
    "balance_btc": 0.005
}

create_context()
create_viewport(title="Prometheu", width=1920, height=1080)
setup_dearpygui()
set_global_font_scale(3.0)

def compactar_json(json_obj):
    json_str = json.dumps(json_obj)
    compressed = zlib.compress(json_str.encode('utf-8'))
    b64 = base64.b64encode(compressed).decode('utf-8')
    return "z1:" + b64  # prefixo para identificar o formato

def descompactar_json(b64_string):
    if not b64_string.startswith("z1:"):
        raise ValueError("Formato de QR desconhecido")
    b64 = b64_string[3:]
    compressed = base64.b64decode(b64)
    json_str = zlib.decompress(compressed).decode('utf-8')
    return json.loads(json_str)

def create_red_button_theme():
    with theme(tag="red_button_theme"):
        with theme_component(mvButton):
            add_theme_color(mvThemeCol_Button, [200, 0, 0], category=mvThemeCat_Core)
            add_theme_color(mvThemeCol_ButtonHovered, [220, 50, 50], category=mvThemeCat_Core)
            add_theme_color(mvThemeCol_ButtonActive, [180, 0, 0], category=mvThemeCat_Core)

create_red_button_theme()

def on_close(sender, app_data, user_data):
    stop_dearpygui()

def attempt_login_callback(sender, app_data, user_data):
    entered = get_value("##password_input")
    if entered == state["password"]:
        state["logged_in"] = True
        delete_item("login_window")
        show_main_window()
    else:
        state["wrong_attempts"] += 1
        if state["wrong_attempts"] >= state["max_attempts"]:
            #delete_item("login_window")
            set_value("login_status", "Dispositivo reiniciado.")
        else:
            set_value("login_status", f"Senha incorreta. Tentativas restantes: {state['max_attempts'] - state['wrong_attempts']}")

def generate_and_show_qrcode():
    reais = get_value("reais_input")
    if reais is None or reais <= 0:
        set_value("valor_status", "Informe um valor válido.")
        return
    else:
        set_value("valor_status", "")  # limpa mensagem de erro

    btc = reais / 300000
    tx = {'payment_hash': '07570eec52b68357c7b1a128c8ebaed18de3edd1c19d0d6df1ac788cfe3c327e',
    'expires_at': 1750811882,
    'bolt11': 'lnbcrt1u1p59yzn2sp5z9mnngyncy68g3ua5xmut793p92n9tapp3gswx3uj897pcnayffqpp5qatsamzjk6p403a35y5v36aw6xx78mw3cxws6m0343ugel3uxflqdqlf9h8vmmfvdjjqer9wd3hy6tsw35k7msxqyjw5qcqp29qxpqysgq7l49ewyf6v94y50k3ymjdkpg5dk9pkshsmlt8gvhsyd4a7ls3p9pdyt228jdwnmfceqe9e2uljr3flqdck7jdxpz6fqwx6ygtcu6maqq04usup',
    'payment_secret': '117739a093c13474479da1b7c5f8b1095532afa10c51071a3c91cbe0e27d2252',
    'created_index': 2,
    'warning_capacity': 'Insufficient incoming channel capacity to pay invoice'}

    # Compacta o JSON e gera o QR
    tx_compactado = compactar_json(tx)

    # Gera imagem do QR Code
    qr = qrcode.make(tx).convert("RGBA").resize((780, 780))
    img_data = np.array(qr, dtype=np.uint8)
    img_data = img_data.astype(np.float32) / 255.0
    img_data_flat = img_data.flatten()

    if does_item_exist("qr_image"):
        delete_item("qr_image")
    if does_item_exist("qr_texture"):
        delete_item("qr_texture")

    with texture_registry(show=False):
        add_static_texture(780, 780, img_data_flat, tag="qr_texture")

    add_image("qr_texture", tag="qr_image", width=780, height=780, parent="qr_child")

def logout_callback():
    state["logged_in"] = False
    state["wrong_attempts"] = 0
    delete_item("Prometheu - Painel Principal")
    show_login_window()

def show_main_window():
    with window(label="Prometheu - Painel Principal",
                width=1920, height=1080,
                pos=[0, 0],
                no_resize=True,
                no_collapse=True,
                on_close=on_close, tag="Prometheu - Painel Principal"):

        with group():
            add_text("Bem-vindo ao Prometheu", bullet=True)
            add_separator()
            add_spacer(height=60)
            add_text(f"Saldo disponível: {state['balance_btc']} BTC")
            add_spacer(height=40)

            add_text("Valor em Reais (R$)")
            add_input_float(tag="reais_input", width=400, step=0.5, step_fast=10.0,
                            min_value=0.0, min_clamped=True)
            add_text("", tag="valor_status", color=[255, 0, 0])  # mensagem de erro aqui

            add_spacer(height=20)
            add_button(label="Gerar QR Code", callback=generate_and_show_qrcode, width=300)
            add_spacer(height=520)

            add_button(label="Logout", callback=logout_callback, width=300)
            bind_item_theme(last_item(), "red_button_theme")

        with child_window(tag="qr_child", width=800, height=800, border=True, pos=[900, 150]):
            pass

def show_login_window():
    with window(label="Login Prometheu",
                width=1920, height=1080,
                pos=[0, 0],
                no_resize=True,
                no_collapse=True,
                on_close=on_close, tag="login_window"):

        add_spacer(height=300)

        with group(horizontal=True):
            add_spacer(width=600)
            with group():
                add_text("Digite a senha:", wrap=400, bullet=False)
                add_spacer(height=60)
                add_input_text(password=True, tag="##password_input", width=700, hint="Senha")
                add_spacer(height=60)
                add_button(label="Entrar", callback=attempt_login_callback, width=700)
                add_spacer(height=20)
                add_text("", tag="login_status", color=[255, 0, 0])
            add_spacer(width=600)

        add_spacer(height=300)

# Início da execução
show_login_window()
show_viewport()
start_dearpygui()
destroy_context()
