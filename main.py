from bip_utils import Bip39MnemonicGenerator, Bip39SeedGenerator, Bip44, Bip44Coins, WifEncoder, CoinsConf, WifPubKeyModes
from pyln.client import LightningRpc
from bitcoinrpc.authproxy import AuthServiceProxy
from bip_utils import Bip44Changes

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

#def create_invoice(msat):
#    inv = rpc.invoice(msat, "testlabel", "Invoice description")
#    return inv

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

    # Checa se a wallet existe ou já está carregada
    try:
        rpc_connection.loadwallet("regtest_wallet")
    except Exception as e:
        print(f"Erro ao carregar wallet: {e}")
    finally:
        # 6. Importa chave privada gerada no Bitcoin Core
        print(f"Saldo da wallet: {rpc_connection.getbalance()}")
        
        rpc_connection.importprivkey(wif_key)
        print("---------------------------")
        print(f"Saldo da wallet: {rpc_connection.getbalance()}")

        # 7. Pega endereço Lightning on-chain
        lightning_address = rpc_node1.newaddr()['bech32']
        print("---------------------------")
        print(f"Endereço on-chain da Lightning wallet: {lightning_address}")

        print("---------------------------")
        for output in rpc_node1.listfunds()['outputs']:
            print(f"Output: {output}")
        for channel in rpc_node1.listchannels()['channels']:
            print(f"Channel: {channel}")

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

        # 10. Verifica saldo
        print("---------------------------")
        print(f"Saldo da wallet: {rpc_connection.getbalance()}")
        for output in rpc_node1.listfunds()['outputs']:
            print(f"Output: {output}")
        for channel in rpc_node1.listchannels()['channels']:
            print(f"Channel: {channel}")

        print("---------------------------")
        print(f"Informações do node 1: {rpc_node1.getinfo()}")
        print(f"Informações do node 2: {rpc_node2.getinfo()}")

        # 11. Conecta-se ao Node 2 e abre canal de pagamento
        node2_info = rpc_node2.getinfo()
        rpc_node1.connect(node2_info['id'], "127.0.0.1", 9737)
        funding_address = rpc_node1.fundchannel(node2_info['id'], 100000)  # 100.000 msat = 0.001 BTC
        print("---------------------------")
        print(f"Canal aberto: {funding_address}")

        rpc_connection.generatetoaddress(6, rpc_connection.getnewaddress())  # Confirma o canal minerando 6 blocos

        # 10. Criar invoice Lightning para 100000 millisatoshis (100 sat)
        node2_invoice = rpc_node2.invoice(100000, "hello___world", "testpayment")
        print("---------------------------")
        print(f"Invoice node 2 gerado: {node2_invoice}")

        # 12. Gera rota de pagamento
        rota = rpc_node1.getroute(node2_info['id'], 100000, 1)
        print("---------------------------")
        print(f"Rota gerada: {rota}")

        rpc_node1.sendpay(rota['route'], node2_invoice['payment_hash'])
        print("---------------------------")
        print(f"Pagamento enviado: {rpc_node1.getroute(node2_info['id'], 100000, 1)}")
        print(f"Payment hash: {node2_invoice['payment_hash']}")
        print(f"Invoices: {rpc_node2.listinvoices()}")
        wait = rpc_node1.waitsendpay(node2_invoice['payment_hash'])
        print(f"Pagamento confirmado: {wait}")

        print("---------------------------")
        for output in rpc_node1.listfunds()['outputs']:
            print(f"Output Node 1: {output}")
        for channel in rpc_node1.listchannels()['channels']:
            print(f"Channel Node 1: {channel}")

        print("---------------------------")
        for output in rpc_node2.listfunds()['outputs']:
            print(f"Output Node 2: {output}")
        for channel in rpc_node2.listchannels()['channels']:
            print(f"Channel Node 2: {channel}")

        print("---------------------------")
        print(f"Informações do node 1: {rpc_node1.getinfo()}")
        print(f"Informações do node 2: {rpc_node2.getinfo()}")