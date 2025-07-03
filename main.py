from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, WifEncoder, CoinsConf, WifPubKeyModes
from pyln.client import LightningRpc
from bitcoinrpc.authproxy import AuthServiceProxy
from bip_utils import Bip44Changes
import uuid
import time

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
    return sum([out["amount_msat"] for out in node_funds["outputs"]]) / 1000  # em satoshis

if __name__ == "__main__":
    print("---------------------------")
    # 1. Gera mnemonics
    mnemonics = generate_mnemonics() # Adicionar a lógica para interação com o usuário caso seja requerido por ele.
    print("MNEMONICS GERADOS:")
    print(mnemonics)
    print("---------------------------")

    # 2. Gera seed a partir do mnemonic
    seed = generate_seed(mnemonics)

    # 3. Gera wallet e pega private key no WIF
    priv_key = generate_wallet(seed)
    print("---------------------------")
    print("priv_key gerada:", priv_key)
    net_ver = CoinsConf.BitcoinTestNet.ParamByKey("wif_net_ver")  # modo testnet/regtest para WIF correto
    wif_key = WifEncoder.Encode(priv_key, net_ver, WifPubKeyModes.COMPRESSED)
    print("---------------------------")
    print("WIF gerado:", wif_key)

    # 4. Conexão RPC Bitcoin Core e Lightning
    rpc_user = "prometheu@prometheu"
    rpc_password = "prometheu"
    rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@127.0.0.1:8332")
    rpc_node = LightningRpc("/home/kauan/.lightning/regtest/lightning-rpc")

    # 5. Cria wallet no Bitcoin Core (se não existir)
    try:
        rpc_connection.createwallet("regtest_wallet", False, False, "", False, False, True)
    except Exception as e:
        print(f"Wallet já existe ou erro ao criar: {e}")

    # 6. Checa se a wallet existe ou já está carregada e importa chave privada
    try:
        rpc_connection.loadwallet("regtest_wallet")
    except Exception as e:
        print(f"Erro ao carregar wallet: {e}")
    finally:
        print(f"Saldo da wallet on-chain: {rpc_connection.getbalance()}")
        rpc_connection.importprivkey(wif_key)
        print("---------------------------")
        print(f"Saldo da wallet on-chain após importação da chave privada: {rpc_connection.getbalance()}")

        # 7. Pega endereço Lightning on-chain
        lightning_address = rpc_node.newaddr()["bech32"]
        print("---------------------------")
        print(f"Endereço on-chain da Lightning wallet: {lightning_address}")
        node_funds_temp = rpc_node.listfunds()
        print(f"Saldo total Node 1: {saldo_total(node_funds_temp)} satoshis") # Se quiserem colocar em reais, façam a conversão.

        # 8. Envia 1 BTC da wallet para a carteira Lightning
        txid = rpc_connection.sendtoaddress(lightning_address, 1) # Colocar aqui o valor que deseja enviar para a Lightning wallet, escolha do usuário (Valor em BTC).
        print("---------------------------")
        print(f"Transação enviada para Lightning. TXID: {txid}")

        # 9. Minerar blocos para confirmar no regtest (gera 3 blocos)
        print("---------------------------")
        print("Minerando blocos para confirmar...")
        rpc_connection.generatetoaddress(3, rpc_connection.getnewaddress())
        print("---------------------------")
        print("Blocos minerados.")

        # 10. Verifica saldo após mineração
        print("---------------------------")
        print(f"Saldo da wallet on-chain: {rpc_connection.getbalance()}")
        node_funds_temp = rpc_node.listfunds()
        print(f"Saldo total Node 1: {saldo_total(node_funds_temp)} satoshis")


        # 13. Criar invoice Lightning para 100000 millisatoshis (100 sat)
        random_label = str(uuid.uuid4())
        node2_invoice = rpc_node.invoice(100000, random_label, "testpayment") # Permitir que o usuário escolha o valor da invoice (aqui está em milisatoshis), label e descrição.
        print("---------------------------")
        print(f"Invoice node 2 gerado: {node2_invoice}")

        # Empacota para o qrcode isso aqui:
        infos_node = {"invoice": node2_invoice, "node": {"lightning_address": lightning_address, "node_id": rpc_node.getinfo()["id"]}}

        # 15. Verifica status da invoice criada
        invoice_status = rpc_node.listinvoices(random_label)
        if invoice_status["invoices"]:
            print(f"Status da invoice {random_label}: {invoice_status['invoices'][-1]['status']}")
            while invoice_status["invoices"][-1]["status"] != "paid":
                print(f"Aguardando pagamento da invoice {random_label}...")
                time.sleep(2)
                invoice_status = rpc_node.listinvoices(random_label)
            print(f"Invoice {random_label} paga.")
        else:
            print(f"Invoice {random_label} não encontrada.")



        # 17. Obter id do canal utilizado para o pagamento (último canal)
        node_funds = rpc_node.listfunds()
        channel_id = None
        if node_funds["channels"]:
            ch = node_funds["channels"][-1]
            channel_id = ch["channel_id"] if "channel_id" in ch else ch.get("short_channel_id")
            print(f"Canal utilizado: {ch}")
        if not channel_id:
            print("Canal não encontrado para fechamento!")
        else:
            # 18. Espera até o canal estar pronto para ser fechado (short_channel_id disponível e estado CHANNELD_NORMAL)
            max_wait = 60  # segundos
            waited = 0
            while (ch["state"] != "CLOSINGD_COMPLETE") and waited < max_wait:
                print(f"Aguardando fechamento do canal... Estado atual: {ch['state']}")
                time.sleep(2)
                waited += 2
                node_funds = rpc_node.listfunds()
                if node_funds["channels"]:
                    ch = node_funds["channels"][-1]

        if ch["state"] != "CLOSINGD_COMPLETE":
            print(f"Canal não fechado: {ch}")
            # raise Exception("Canal não fechado!")
        else:
            print(f"Canal fechado com sucesso: {ch}")

        # 19. Printar saldo total dos nodes
        node_total = saldo_total(rpc_node.listfunds())
        print(f"Saldo total Node 1: {node_total} satoshis")