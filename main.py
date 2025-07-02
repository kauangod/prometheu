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
    return sum([out['amount_msat'] for out in node_funds['outputs']]) / 1000  # em satoshis

if __name__ == "__main__":
    print("---------------------------")
    # 1. Gera mnemonics
    mnemonics = generate_mnemonics()
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
    rpc_user = 'kauan_rpc'
    rpc_password = 'senharpc'
    rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@127.0.0.1:18443")
    rpc_node1 = LightningRpc("/home/kauan/.lightning/regtest/lightning-rpc")  # Ajuste o caminho
    rpc_node2 = LightningRpc("/home/kauan/.lightning2/regtest/lightning-rpc")

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
        lightning_address = rpc_node1.newaddr()['bech32'] # salvar esse endereço em um arquivo e depois só gerar o endereço caso o arquivo esteja vazio
        print("---------------------------")
        print(f"Endereço on-chain da Lightning wallet: {lightning_address}")
        node1_funds_temp = rpc_node1.listfunds()
        print(f"Saldo total Node 1: {saldo_total(node1_funds_temp)} satoshis")

        # 8. Envia 1 BTC da wallet para a carteira Lightning
        txid = rpc_connection.sendtoaddress(lightning_address, 1)
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
        node1_funds_temp = rpc_node1.listfunds()
        print(f"Saldo total Node 1: {saldo_total(node1_funds_temp)} satoshis")

        print("---------------------------")
        print(f"Informações do node 1: {rpc_node1.getinfo()}")
        print(f"Informações do node 2: {rpc_node2.getinfo()}")

        # 11. Conecta-se ao Node 2 e abre canal de pagamento
        node2_info = rpc_node2.getinfo()
        rpc_node1.connect(node2_info['id'], "127.0.0.1", 9737)
        funding_address = rpc_node1.fundchannel(node2_info['id'], '50000sat')  # 100.000 msat = 0.001 BTC
        print("---------------------------")
        print(f"Canal aberto: {funding_address}")

        # 12. Confirma o canal minerando 6 blocos
        rpc_connection.generatetoaddress(6, rpc_connection.getnewaddress())

        # 13. Criar invoice Lightning para 100000 millisatoshis (100 sat)
        random_label = str(uuid.uuid4())
        node2_invoice = rpc_node2.invoice(100000, random_label, "testpayment")
        print("---------------------------")
        print(f"Invoice node 2 gerado: {node2_invoice}")

        # 14. Realiza pagamento via pay (mais estável que sendpay)
        pay_result = rpc_node1.pay(node2_invoice['bolt11'])
        print("---------------------------")
        print(f"Pagamento enviado: {pay_result}")
        print(f"Payment hash: {node2_invoice['payment_hash']}")
        print(f"Invoices: {rpc_node2.listinvoices()}")

        # 15. Verifica status da invoice criada
        invoice_status = rpc_node2.listinvoices(random_label)
        if invoice_status['invoices']:
            print(f"Status da invoice {random_label}: {invoice_status['invoices'][0]['status']}")
        else:
            print(f"Invoice {random_label} não encontrada.")

        # 16. Obter endereço do node2 (receptor)
        node2_address = rpc_node2.newaddr()['bech32']
        print("---------------------------")
        print(f"Endereço do node 2 (receptor): {node2_address}")

        # 17. Obter id do canal utilizado para o pagamento (último canal)
        node1_funds = rpc_node1.listfunds()
        channel_id = None
        if node1_funds['channels']:
            ch = node1_funds['channels'][-1]
            channel_id = ch['channel_id'] if 'channel_id' in ch else ch.get('short_channel_id')
            print(f"Canal utilizado: {ch}")
        if not channel_id:
            print("Canal não encontrado para fechamento!")
        else:
            # 18. Espera até o canal estar pronto para ser fechado (short_channel_id disponível e estado CHANNELD_NORMAL)
            max_wait = 60  # segundos
            waited = 0
            while ('short_channel_id' not in ch or ch['state'] != 'CHANNELD_NORMAL') and waited < max_wait:
                print(f"Aguardando canal lockin... Estado atual: {ch['state']}")
                time.sleep(2)
                waited += 2
                node1_funds = rpc_node1.listfunds()
                if node1_funds['channels']:
                    ch = node1_funds['channels'][-1]
            if 'short_channel_id' not in ch or ch['state'] != 'CHANNELD_NORMAL':
                raise Exception('Canal não ficou pronto para fechamento (lockin) após tempo limite!')
            short_channel_id = ch['short_channel_id']
            close_result = rpc_node1.close(short_channel_id, 0, destination=node2_address)
            print(f"Resultado do fechamento do canal (com short_channel_id): {close_result}")

        # 19. Printar saldo total dos nodes
        node1_total = saldo_total(rpc_node1.listfunds())
        node2_total = saldo_total(rpc_node2.listfunds())
        print(f"Saldo total Node 1: {node1_total} satoshis")
        print(f"Saldo total Node 2: {node2_total} satoshis")