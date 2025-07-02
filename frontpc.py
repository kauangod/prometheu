from dearpygui.dearpygui import *
import hashlib
import json
import qrcode
import numpy as np
import os

# -------------------- ESTADO GLOBAL --------------------
state = {
    "logged_in": False,
    "wrong_attempts": 0,
    "max_attempts": 3,
    "password_set": False,
    "balance_btc": 0.005,
    "current_screen": "initial"  # controle da tela atual
}

# -------------------- DEARPYGUI --------------------
create_context()
create_viewport(title="Prometheu", width=1920, height=1080)
setup_dearpygui()
set_global_font_scale(3.0)

# -------------------- UTILITÁRIOS --------------------
def hash_sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

def create_red_button_theme():
    with theme(tag="red_button_theme"):
        with theme_component(mvButton):
            add_theme_color(mvThemeCol_Button, [200, 0, 0], category=mvThemeCat_Core)
            add_theme_color(mvThemeCol_ButtonHovered, [220, 50, 50], category=mvThemeCat_Core)
            add_theme_color(mvThemeCol_ButtonActive, [180, 0, 0], category=mvThemeCat_Core)
create_red_button_theme()

def on_close(sender, app_data, user_data):
    stop_dearpygui()

# -------------------- FUNÇÃO AUXILIAR DE TROCA DE TELAS --------------------
def switch_window(old_tag, new_window_func, new_screen_name):
    if does_item_exist(old_tag):
        delete_item(old_tag)
    state["current_screen"] = new_screen_name
    new_window_func()

# -------------------- TELAS POR ESTADO --------------------

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

                add_button(label="Criar carteira automaticamente", width=700, callback=criar_carteira)
                add_spacer(height=20)

                add_button(label="Inserir carteira existente", width=700, callback=mostrar_campo_mnemonicos)
                add_spacer(height=20)

                add_input_text(multiline=True, tag="mnemonic_input", hint="Insira as 24 palavras separadas por espaço", width=700, height=100)
                hide_item("mnemonic_input")

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
    with window(label="Prometheu - Painel Principal", width=1920, height=1080, pos=[0, 0], no_resize=True, no_collapse=True, on_close=on_close, tag="main_window"):
        with group():
            add_text("Bem-vindo ao Prometheu", bullet=True)
            add_separator()
            add_spacer(height=60)
            add_text(f"Saldo disponível: {state['balance_btc']} BTC")
            add_spacer(height=40)

            add_text("Valor em Reais (R$)")
            add_input_float(tag="reais_input", width=400, step=0.5, step_fast=10.0, min_value=0.0, min_clamped=True)
            add_text("", tag="valor_status", color=[255, 0, 0])
            add_spacer(height=20)

            add_button(label="Gerar QR Code", callback=generate_and_show_qrcode, width=300)
            add_spacer(height=520)

            add_button(label="Logout", callback=logout_callback, width=300)
            bind_item_theme(last_item(), "red_button_theme")

        with child_window(tag="qr_child", width=800, height=800, border=True, pos=[900, 150]):
            pass

# -------------------- FUNÇÕES DE AÇÃO --------------------

def criar_carteira():
    mock_words = ["word" + str(i) for i in range(1, 25)]
    show_item("mnemonic_input")
    set_value("mnemonic_input", " ".join(mock_words))
    set_value("register_status", "Carteira gerada automaticamente. Você pode prosseguir.")

def mostrar_campo_mnemonicos():
    show_item("mnemonic_input")
    set_value("mnemonic_input", "")
    set_value("register_status", "Insira as 24 palavras da sua carteira.")

def handle_register():
    pwd = get_value("##new_password_input")
    mnemonic = get_value("mnemonic_input").strip().split()

    if not (pwd.isdigit() and len(pwd) == 4):
        set_value("register_status", "A senha deve conter exatamente 4 números.")
        return

    if not mnemonic or len(mnemonic) != 24:
        set_value("register_status", "Você deve inserir exatamente 24 palavras.")
        return

    with open("pin", "w") as f:
        f.write(hash_sha256(pwd))

    with open("mnemonics", "w") as f:
        f.write(" ".join(mnemonic))

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
        state["logged_in"] = True
        state["wrong_attempts"] = 0  # Zera o contador porque acertou
        switch_window("login_window", create_main_window, "main")
    else:
        state["wrong_attempts"] += 1
        tentativas_restantes = state["max_attempts"] - state["wrong_attempts"]
        if state["wrong_attempts"] >= state["max_attempts"]:
            # Apaga arquivos e reseta estado
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

def generate_and_show_qrcode():
    reais = get_value("reais_input")
    if reais is None or reais <= 0:
        set_value("valor_status", "Informe um valor válido.")
        return
    set_value("valor_status", "")

    tx = {
        'payment_hash': '07570eec52b68357c7b1a128c8ebaed18de3edd1c19d0d6df1ac788cfe3c327e',
        'expires_at': 1750811882,
        'bolt11': 'lnbcrt1u1p59yzn2sp5z9mnngyncy68g3ua5xmut793p92n9tapp3gswx3uj897pcnayffqpp...',
        'payment_secret': '117739a093c13474479da1b7c5f8b1095532afa10c51071a3c91cbe0e27d2252',
        'created_index': 2,
        'warning_capacity': 'Insufficient incoming channel capacity to pay invoice'
    }

    # Aqui o JSON está usado sem compactação
    json_text = json.dumps(tx)

    qr = qrcode.make(json_text).convert("RGBA").resize((780, 780))
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

# -------------------- EXECUÇÃO --------------------
create_initial_window()
state["current_screen"] = "initial"

show_viewport()
start_dearpygui()
destroy_context()
