import Charts
import SwiftUI

struct BarraAno: Identifiable {
    let ano: Int
    let postos: Int
    var id: Int { ano }
}

struct PostosView: View {
    @EnvironmentObject private var estado: EstadoApp
    @State private var ordem = [KeyPathComparator(\PostoDTO.id)]

    var body: some View {
        let reg = estado.regiao
        let lista = estado.postosFiltrados.sorted(using: ordem)
        let barras = (estado.dados.postosPorAno[reg] ?? []).map { BarraAno(ano: $0.ano, postos: $0.postos) }.sorted { $0.ano < $1.ano }
        let rotulos = barras.map { String($0.ano) }.filter { (Int($0) ?? 0) % 5 == 0 }

        VStack(alignment: .leading, spacing: 18) {
            CabecalhoRegiao(subtitulo: "\(Fmt.num(Double(estado.postosNaRegiao(reg).count), 0)) postos com dados desde 1980 (GHCN-Daily: ANA e DAEE)")
            Cartao("Postos com dado em cada ano", nota: "O gráfico mostra quando a rede do GHCN-Daily encolhe em SP. Os anos recentes dependem do HidroWeb (ANA) e do SIBH (DAEE).") {
                Chart(barras) { b in
                    BarMark(x: .value("Ano", String(b.ano)), y: .value("Postos", b.postos))
                        .foregroundStyle(Produto.CHIRPS.cor)
                        .cornerRadius(2)
                }
                .chartXAxis {
                    AxisMarks(values: rotulos) { _ in
                        AxisValueLabel()
                    }
                }
                .frame(height: 220)
            }
            Cartao("Lista de postos", nota: "Clique no título de uma coluna para ordenar. O botão Exportar CSV salva a lista filtrada.") {
                HStack {
                    TextField("Buscar por nome, código ou rede (ex.: Bauru, E3-052, ANA)", text: $estado.busca)
                        .textFieldStyle(.roundedBorder)
                        .frame(maxWidth: 420)
                    Text("\(lista.count) postos").foregroundStyle(.secondary).monospacedDigit()
                }
                Table(lista, sortOrder: $ordem) {
                    TableColumn("Código GHCN", value: \.id)
                    TableColumn("Nome", value: \.nome)
                    TableColumn("Rede", value: \.rede)
                    TableColumn("Código original", value: \.codigoOriginal)
                    TableColumn("UGRHI", value: \.sigla)
                    TableColumn("Início", value: \.inicio)
                    TableColumn("Fim", value: \.fim)
                    TableColumn("Dias com dado", value: \.dias) { p in
                        Text(Fmt.num(Double(p.dias), 0)).monospacedDigit()
                    }
                }
                .frame(height: 440)
            }
        }
    }
}
