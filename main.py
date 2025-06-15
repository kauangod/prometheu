from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins
from pyln.client import LightningRpc
from bitcoinlib.wallets import HDWallet
from bitcoinrpc.authproxy import AuthServiceProxy
from bitcoinlib.keys import HDKey
from bitcoinlib.transactions import Transaction, Output
from state import State
import re
import hashlib

want_own_mnemonics = False # Definir a partir da interação do usuário com a interface

def generate_mnemonics():
    return Bip39MnemonicGenerator().FromWordsNumber(24)

# 2. Generate seed from mnemonics
def generate_seed(mnemonics):
    return Bip39SeedGenerator(mnemonics).Generate()

# 3. Generate BIP44 wallet for Bitcoin regtest
def generate_wallet(seed_bytes):
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0)
    bip44_change_ctx = bip44_acc_ctx.Change(0)
    bip44_addr_ctx = bip44_change_ctx.AddressIndex(0)
    return bip44_addr_ctx.PrivateKey().ToWif()

def create_invoice(msat):
    inv = rpc.invoice(msat, "testlabel", "Invoice description")
    return inv['bolt11']

# 6. Pay invoice
def pay_invoice(bolt11):
    pay_res = rpc.pay(bolt11)
    return pay_res

def check_pin_already_set():
    with open("/home/kauan/.prometheu/pin", "r") as f: # Mudar caminho no PI
        if f.read() == "":
            return False
        else:
            return True

def mnem_definition():
    if want_own_mnemonics:
        mnemonics_list = []
        mnemonics = input_mnem(mnemonics_list)
    else:
        state.add_state("MNEM_GEN")
        mnemonics = generate_mnemonics()
        state.pop_state()
    with open("/home/kauan/.prometheu/mnemonics", "w") as f:
            f.write(mnemonics)

def input_mnem(mnemonics_list):
    word_number = 24
    i = 0
    print("Digite suas 24 palavras mnemônicas: ")
    while i < word_number:
        word = input(f"{word_number} palavras restantes: ")
        if re.match(r"^[a-zA-Z]+$", word) is None:
            print("Digite uma palavra válida (apenas letras, sem acentuação ou caracteres especiais)")
            continue
        else:
            mnemonics_list.append(word)
            i += 1
    return " ".join(mnemonics_list)

if __name__ == "__main__":
    state = State()


    if check_pin_already_set():
        state.add_state("PIN_CHK")
    else:
        state.add_state("PIN_REG")
        while (state.get_current_state() == "PIN_REG"):
            pin = input("Registre o PIN de quatro dígitos do seu wallet (apenas números, sem espaços): ")
            if len(pin) != 4 or re.match(r"^[0-9]+$", pin) is None:
                print("Digite um PIN válido")
                continue
            else:
                with open("/home/kauan/.prometheu/pin", "w") as f:
                    f.write(hashlib.sha256(pin.encode('UTF-8')).hexdigest())
                    state.pop_state()
                    state.add_state("PIN_CHK")
                    break

    while (state.get_current_state() == "PIN_CHK"):
        pin_input = input("Digite o PIN de quatro dígitos do seu wallet (apenas números, sem espaços): ")
        if hashlib.sha256(pin_input.encode('UTF-8')).hexdigest() != f.read():
            print("Tente novamente")
            continue
        else:
            state.pop_state()
            with open("/home/kauan/.prometheu/mnemonic", "r") as f:
                if (f.read() != ""):
                    state.add_state("MAIN_MENU")
                    break
                else:
                    state.add_state("MNEM_REG")
                    break

    while (state.get_current_state() == "MNEM_REG"):
        mnem_definition()
        state.pop_state()

    with open("/home/kauan/.prometheu/mnemonics", "r") as f:
        mnemonics = f.read()

    seed = generate_seed(mnemonics)
    wallet = generate_wallet(seed)

    rpc_user = 'kauan_rpc'
    rpc_password = 'senharpc'
    rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@127.0.0.1:18443")
    rpc = LightningRpc("/home/kauan/.lightning/regtest/lightning-rpc") # Mudar caminho no PI

    try:
        rpc_connection.createwallet("prometheu_wallet", False, True)
    except Exception as e:
        print(f"Erro ao criar wallet: {e}")

    rpc_connection.loadwallet("prometheu_wallet")
    rpc_connection.importprivkey(wallet)
    lightning_address = rpc.newaddr()['address']
    rpc_connection.sendtoaddress(lightning_address, 0.001) ## Mandando satoshis para a carteira Lightning

    # Create invoice for 100000 msat (100 satoshis)
    bolt11 = create_invoice(100000)
    print("Created invoice:", bolt11)