#!/bin/bash
# Monta "Chuva SP.app" (Apple Silicon e Intel) a partir do código em ChuvaSP/.
# Requisitos no Mac: Ferramentas de Linha de Comando do Xcode (xcode-select --install).
# Uso: bash macos/construir_app.sh    → cria macos/build/Chuva SP.app e o .zip
set -euo pipefail
cd "$(dirname "$0")"

NOME="Chuva SP"
APP="build/$NOME.app"
MIN="14.0"
FONTES=(ChuvaSP/Fontes/Nucleo/*.swift ChuvaSP/Fontes/App/*.swift)

rm -rf build
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" build/obj

echo "== Compilando (Swift $(swiftc --version 2>&1 | head -1))"
for ARQ in arm64 x86_64; do
  swiftc -O -swift-version 5 -parse-as-library \
    -target "$ARQ-apple-macos$MIN" \
    -module-name ChuvaSP \
    "${FONTES[@]}" -o "build/obj/ChuvaSP-$ARQ"
done
lipo -create build/obj/ChuvaSP-arm64 build/obj/ChuvaSP-x86_64 -output "$APP/Contents/MacOS/ChuvaSP"

echo "== Recursos"
cp ChuvaSP/Info.plist "$APP/Contents/Info.plist"
cp -R ChuvaSP/Dados "$APP/Contents/Resources/Dados"
if [ -f ChuvaSP/Icone/icone_1024.png ]; then
  ICONSET="build/Icone.iconset"
  mkdir -p "$ICONSET"
  for T in 16 32 128 256 512; do
    sips -z $T $T ChuvaSP/Icone/icone_1024.png --out "$ICONSET/icon_${T}x${T}.png" >/dev/null
    sips -z $((T * 2)) $((T * 2)) ChuvaSP/Icone/icone_1024.png --out "$ICONSET/icon_${T}x${T}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/Icone.icns"
fi

echo "== Assinatura local (ad hoc)"
codesign --force --deep --sign - "$APP"
codesign --verify --verbose=2 "$APP"

(cd build && ditto -c -k --keepParent "$NOME.app" "Chuva-SP-macOS.zip")
echo "Pronto: macos/$APP"
echo "Arquivo para distribuir: macos/build/Chuva-SP-macOS.zip"
