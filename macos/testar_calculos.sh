#!/bin/bash
# Compila o núcleo de cálculo do app e compara com valores do ClimdexSP em R.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
swiftc -O -swift-version 5 ChuvaSP/Fontes/Nucleo/*.swift ChuvaSP/Testes/main.swift -o build/testes
build/testes ChuvaSP/Dados ChuvaSP/Testes/referencia_climdexsp.json
