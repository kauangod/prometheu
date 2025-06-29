#!/bin/bash

LOGFILE="diagnostic_lightning.log"

# Limpa o log anterior e cria novo
> "$LOGFILE"

# Redireciona toda a saída para o log
exec > >(tee -a "$LOGFILE") 2>&1

# Diretórios dos nodes
NODE1_DIR="$HOME/.lightning"
NODE2_DIR="$HOME/.lightning2"

# Comando lightning-cli
CLI="lightning-cli --regtest"

# Função para printar título
print_title() {
  echo -e "\n==================== $1 ====================\n"
}

print_title "Node 1 - getinfo"
$CLI --lightning-dir=$NODE1_DIR getinfo

print_title "Node 2 - getinfo"
$CLI --lightning-dir=$NODE2_DIR getinfo

print_title "Node 1 - listpeers (com channels)"
$CLI --lightning-dir=$NODE1_DIR listpeers

print_title "Node 2 - listpeers (com channels)"
$CLI --lightning-dir=$NODE2_DIR listpeers

print_title "Node 1 - listchannels"
$CLI --lightning-dir=$NODE1_DIR listchannels

print_title "Node 2 - listchannels"
$CLI --lightning-dir=$NODE2_DIR listchannels

print_title "Node 1 - listfunds"
$CLI --lightning-dir=$NODE1_DIR listfunds

print_title "Node 2 - listfunds"
$CLI --lightning-dir=$NODE2_DIR listfunds

print_title "Node 2 - listinvoices hello_world"
$CLI --lightning-dir=$NODE2_DIR listinvoices hello_world