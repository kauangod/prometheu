#!/bin/bash

set -e

echo "==== Atualizando sistema ===="
sudo apt update && sudo apt upgrade -y

echo "==== Instalando dependências de sistema ===="
sudo apt install -y build-essential autoconf libtool pkg-config libevent-dev libboost-system-dev libboost-filesystem-dev libboost-test-dev libssl-dev libsqlite3-dev python3 python3-pip python3-venv git libgmp-dev zlib1g-dev libsodium-dev

echo "==== Clonando e compilando Bitcoin Core (bitcoind) ===="
cd ~
if [ ! -d bitcoin ]; then
    git clone https://github.com/bitcoin/bitcoin.git
fi
cd bitcoin
./autogen.sh
./configure --without-gui
make -j$(nproc)
sudo make install
cd ~

echo "==== Criando bitcoin.conf ===="
mkdir -p ~/.bitcoin
cat <<EOF > ~/.bitcoin/bitcoin.conf
[regtest]
server=1
rpcuser=prometheu@prometheu
rpcpassword=prometheu@prometheu
rpcbind=127.0.0.1
rpcallowip=127.0.0.1
txindex=1
fallbackfee=0.0002
EOF

echo "==== Iniciando bitcoind ===="
bitcoind -regtest -daemon
sleep 10

echo "==== Criando wallet 'regtest_wallet' (se ainda não existir) ===="
wallets=$(bitcoin-cli -regtest -rpcuser=prometheu@prometheu -rpcpassword=prometheu@prometheu listwallets)
if [[ $wallets != *"regtest_wallet"* ]]; then
    bitcoin-cli -regtest -rpcuser=prometheu@prometheu -rpcpassword=prometheu@prometheu createwallet regtest_wallet
fi

echo "==== Gerando 101 blocos para liberar saldo na wallet ===="
ADDRESS=$(bitcoin-cli -regtest -rpcuser=prometheu@prometheu -rpcpassword=prometheu@prometheu -rpcwallet=regtest_wallet getnewaddress)
bitcoin-cli -regtest -rpcuser=prometheu@prometheu -rpcpassword=prometheu@prometheu -rpcwallet=regtest_wallet generatetoaddress 101 $ADDRESS

echo "==== Verificando blockchain e saldo ===="
bitcoin-cli -regtest -rpcuser=prometheu@prometheu -rpcpassword=prometheu@prometheu -rpcwallet=regtest_wallet getblockchaininfo
bitcoin-cli -regtest -rpcuser=prometheu@prometheu -rpcpassword=prometheu@prometheu -rpcwallet=regtest_wallet getbalance

echo "==== Clonando e compilando Core Lightning ===="
cd ~
if [ ! -d lightning ]; then
    git clone https://github.com/ElementsProject/lightning.git
fi
cd lightning
./configure
make -j$(nproc)
sudo make install

echo "==== Criando ambiente virtual Python ===="
cd ~
python3 -m venv lightning_env
source ~/lightning_env/bin/activate

echo "==== Instalando pacotes Python no ambiente virtual ===="
pip install --upgrade pip
pip install -r requirements.txt

echo "==== Iniciando lightningd apontando para regtest wallet ===="
# mata processo lightningd anterior, se existir
pkill lightningd || true

lightningd --network=regtest --log-level=debug --bitcoin-rpcuser=prometheu@prometheu --bitcoin-rpcpassword=prometheu@prometheu --bitcoin-rpcconnect=127.0.0.1 --bitcoin-rpcport=18443 --bitcoin-rpcwallet=regtest_wallet &

sleep 5

mkdir -p ~/.prometheu
touch ~/.prometheu/pin
touch ~/.prometheu/mnemonics


echo "==== Setup completo ===="

echo "Bitcoind e Lightningd já estão rodando no regtest com wallet ativada e saldo para testes!"



