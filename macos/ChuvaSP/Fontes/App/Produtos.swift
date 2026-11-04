import SwiftUI

struct ProdutosView: View {
    @EnvironmentObject private var estado: EstadoApp

    private static let repositorio = "https://github.com/rafagsanches-cloud/blank-app/blob/claude/happy-brahmagupta-udhdxu/"
    private struct Arquivo: Identifiable {
        let titulo: String
        let caminho: String
        var id: String { caminho }
    }

    private static let arquivos: [Arquivo] = [
        Arquivo(titulo: "Excel principal: anual, mensal, diário, postos e validação", caminho: "saidas/Chuva_SP_1980-2026_satelites_e_postos.xlsx"),
        Arquivo(titulo: "Excel horário do CMORPH", caminho: "saidas/Chuva_SP_horario_CMORPH_1998-2026.xlsx"),
        Arquivo(titulo: "Excel horário do IMERG", caminho: "saidas/Chuva_SP_horario_IMERG_1998-2026.xlsx"),
        Arquivo(titulo: "Shapefile das UGRHIs", caminho: "dados/ugrhi/UGRHI_SP_shapefile.zip"),
        Arquivo(titulo: "UGRHIs como objeto sf do R (.rds)", caminho: "dados/ugrhi/ugrhi_sp.rds"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Produtos e fontes").font(.system(size: 28, weight: .regular, design: .serif))
            Cartao("Produtos de satélite", nota: "A tabela pedida, com a versão de cada produto usada aqui e o período baixado.") {
                Grid(alignment: .topLeading, horizontalSpacing: 16, verticalSpacing: 10) {
                    GridRow {
                        ForEach(["Produto", "Tipo de sensor principal", "Série histórica", "Resolução espacial", "Foco principal", "Versão usada", "Período baixado"], id: \.self) { c in
                            Text(c).fontWeight(.medium)
                        }
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    Divider().gridCellUnsizedAxes(.horizontal)
                    ForEach(estado.dados.produtos) { p in
                        GridRow {
                            HStack(spacing: 6) {
                                Circle().fill((Produto(rawValue: p.produto) ?? .POSTOS).cor).frame(width: 8, height: 8)
                                Text(p.produto).fontWeight(.medium)
                            }
                            Text(p.sensor)
                            Text(p.serie)
                            Text(p.resolucao)
                            Text(p.foco).frame(maxWidth: 220, alignment: .leading)
                            Text(p.versao)
                            Text(p.periodo).foregroundStyle(.secondary)
                        }
                        .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .font(.callout)
            }
            HStack(alignment: .top, spacing: 12) {
                Cartao("Bases de dados") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(estado.dados.fontes) { f in
                            VStack(alignment: .leading, spacing: 1) {
                                if let url = URL(string: f.endereco) {
                                    Link(f.base, destination: url)
                                } else {
                                    Text(f.base)
                                }
                                Text("\(f.grupo) · \(f.descricao)").font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
                VStack(spacing: 12) {
                    Cartao("Arquivos para baixar", nota: "No GitHub. O Excel abre no Numbers.") {
                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(ProdutosView.arquivos) { item in
                                if let url = URL(string: ProdutosView.repositorio + item.caminho) {
                                    Link(item.titulo, destination: url)
                                }
                            }
                        }
                    }
                    Cartao("Como os números foram feitos") {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Cada pixel entra na média da UGRHI com peso igual à fração da sua área dentro dela, multiplicada pelo cosseno da latitude. A média só é calculada quando pelo menos metade da área tem dado.")
                            Text("As faltas seguem o RClimDex: o mês fica em branco com mais de 3 dias sem dado e o ano com mais de 15. Os dias dos satélites vão de 0 h a 24 h UTC.")
                            Text("Os índices ETCCDI deste app foram conferidos contra o ClimdexSP em R, que por sua vez coincide com o pacote climdex.pcic.")
                            Text("O CMORPH fica abaixo dos outros produtos em todo o Estado; a soma das 24 horas reproduz o arquivo diário oficial, então a diferença é do próprio produto. O IMERG usado é a versão Late Run v07.")
                        }
                        .font(.callout)
                        .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
    }
}
