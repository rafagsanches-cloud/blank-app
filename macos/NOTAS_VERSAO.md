App nativo para macOS (Apple Silicon e Intel, macOS 14 Sonoma ou mais novo, inclusive macOS 26 Tahoe) com a chuva do Estado de São Paulo por UGRHI: satélites CHIRPS, IMERG, PERSIANN, CMORPH e GPCP e os postos pluviométricos da ANA e do DAEE (GHCN-Daily), de 1980 a 2026. Os dados vão dentro do app; ele funciona sem internet.

Novo: as séries diárias das estações pluviométricas da ANA em SP, baixadas do HidroWeb (web service da ANA, o mesmo usado pelo pyHidroWeb e pelo hydrobr). A média dos postos da ANA aparece como mais uma série, "ANA (HidroWeb)", nos gráficos e nos índices de extremos (dá para esconder no botão Produtos). A tela nova "Postos da ANA" lista as estações com a série de cada uma, e a tela Satélite × postos pode comparar os satélites com os postos da ANA.

Como instalar
1. Baixe `Chuva-SP-macOS.zip` abaixo e abra o arquivo (o Finder descompacta).
2. Arraste `Chuva SP.app` para a pasta Aplicativos.
3. Na primeira vez, o macOS avisa que não pode verificar o desenvolvedor (o app não é assinado pela Apple). Abra Ajustes do Sistema > Privacidade e Segurança, role até o aviso sobre "Chuva SP" e clique em "Abrir Mesmo Assim". Outra opção, no Terminal: `xattr -dr com.apple.quarantine "/Applications/Chuva SP.app"`.

As imagens `*_claro.png` e `*_escuro.png` mostram cada tela, geradas automaticamente na compilação.
