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

def create_invoice(msat):
    inv = rpc.invoice(msat, "LABEL PRO PEDRO", "Invoice description")
    return inv

if __name__ == "__main__":
    # 1. Gera mnemonics
    mnemonics = generate_mnemonics()
    print("MNEMONICS GERADOS:")
    print(mnemonics)

    # 2. Gera seed a partir do mnemonic
    seed = generate_seed(mnemonics)

    # 3. Gera wallet e pega private key no WIF
    priv_key = generate_wallet(seed)
    print("priv_key gerada:", priv_key)
    net_ver = CoinsConf.BitcoinTestNet.ParamByKey("wif_net_ver") # Está no modo testnet/regtest, para devolver o WIF no formato correto
    wif_key = WifEncoder.Encode(priv_key, net_ver, WifPubKeyModes.COMPRESSED)
    print("WIF gerado:", wif_key)

    # 4. Conexão RPC Bitcoin Core e Lightning
    rpc_user = 'kauan_rpc'
    rpc_password = 'senharpc'
    rpc_connection = AuthServiceProxy(f"http://{rpc_user}:{rpc_password}@127.0.0.1:18443")
    rpc = LightningRpc("/home/kauan/.lightning/regtest/lightning-rpc")  # Ajuste o caminho

    # 5. Cria wallet no Bitcoin Core (se não existir)
    try:
        rpc_connection.createwallet("regtest_wallet", False, False, "", False, False, True)
    except Exception as e:
        print(f"Wallet já existe ou erro ao criar: {e}")

    try:
        rpc_connection.loadwallet("regtest_wallet")
    except Exception as e:
        print(f"Erro ao carregar wallet: {e}")
    finally:
        # 6. Importa chave privada gerada no Bitcoin Core
        # print(f"Saldo da wallet: {rpc_connection.getbalance()}")
        # address = rpc_connection.getnewaddress()
        # print(f"Endereço gerado: {address}")
        # rpc_connection.generatetoaddress(101, address)
        # print(f"Saldo da wallet: {rpc_connection.getbalance()}")

        rpc_connection.importprivkey(wif_key)
        print(f"Saldo da wallet: {rpc_connection.getbalance()}")

        # 7. Pega endereço Lightning on-chain
        lightning_address = rpc.newaddr()['bech32']
        print(f"Endereço on-chain da Lightning wallet: {lightning_address}")
        for output in rpc.listfunds()['outputs']:
            print(f"Output: {output}")
        for channel in rpc.listchannels()['channels']:
            print(f"Channel: {channel}")
        # 8. Envia 0.001 BTC da wallet para a carteira Lightning
        txid = rpc_connection.sendtoaddress(lightning_address, 10)
        print(f"Transação enviada para Lightning. TXID: {txid}")

        # 9. Minerar blocos para confirmar no regtest (gera 3 blocos)
        print("Minerando blocos para confirmar...")
        rpc_connection.generatetoaddress(3, rpc_connection.getnewaddress())
        print("Blocos minerados.")

        # 10. Verifica saldo
        print(f"Saldo da wallet: {rpc_connection.getbalance()}")
        for output in rpc.listfunds()['outputs']:
            print(f"Output: {output}")
        for channel in rpc.listchannels()['channels']:
            print(f"Channel: {channel}")
        # print(f"Saldo da Lightning wallet: {rpc.listfunds()}")
        # 10. Criar invoice Lightning para 100000 millisatoshis (100 sat)
        bolt11 = create_invoice(100000)
        print(f"Invoice gerado: {bolt11}")