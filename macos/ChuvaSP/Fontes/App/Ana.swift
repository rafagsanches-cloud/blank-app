import Charts
import SwiftUI

/// Barra simples (ano ou mês) para os gráficos do posto selecionado.
struct BarraValor: Identifiable {
    let x: Int
    let y: Double
    var id: Int { x }
}

private let nomesMeses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

/// "1980-01-01" -> "01/01/1980"
func dataBR(_ s: String) -> String {
    let p = s.split(separator: "-")
    return p.count == 3 ? "\(p[2])/\(p[1])/\(p[0])" : s
}

struct AnaView: View {
    @EnvironmentObject private var estado: EstadoApp
    @State private var ordem = [KeyPathComparator(\AnaPostoDTO.id)]

    var body: some View {
        let reg = estado.regiao
        let todos = estado.anaPostosNaRegiao(reg)
        let lista = estado.anaPostosFiltrados.sorted(using: ordem)
        let barras = (estado.dados.anaPostosPorAno[reg] ?? []).map { BarraAno(ano: $0.ano, postos: $0.postos) }.sorted { $0.ano < $1.ano }
        let rotulos = barras.map(\.ano).filter { $0 % 5 == 0 }.map { String($0) }
        let inventario = estado.dados.anaResumo?.inventario[reg] ?? 0
        let recentes = todos.filter { $0.fim >= "2021-01-01" }.count
        let produtos = [Produto.ANA] + Produto.satelites.filter { estado.visiveis.contains($0) }
        let pontos = produtos.flatMap { p in
            pontosEmSegmentos(p, estado.serieAnual(p, reg).map { (x: $0.ano, y: $0.mm) })
        }
        let anos = pontos.map(\.x)

        VStack(alignment: .leading, spacing: 18) {
            CabecalhoRegiao(subtitulo: "Estações pluviométricas da ANA (HidroWeb), séries diárias desde 1980")
            if estado.dados.anaPostos.isEmpty {
                Text("Os dados da ANA não estão na pasta Dados deste app.").foregroundStyle(.secondary)
            } else {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 12)], spacing: 12) {
                    CartaoNumero(rotulo: "Estações pluviométricas no inventário da ANA",
                                 valor: Fmt.num(Double(inventario), 0), unidade: "estações",
                                 nota: "Convencionais e automáticas, nesta região")
                    CartaoNumero(rotulo: "Com série diária desde 1980",
                                 valor: Fmt.num(Double(todos.count), 0), unidade: "postos",
                                 nota: "Pelo menos um ano de dados no HidroWeb")
                    CartaoNumero(rotulo: "Com dado depois de 2020",
                                 valor: Fmt.num(Double(recentes), 0), unidade: "postos",
                                 nota: "Último dia com dado em 2021 ou depois")
                    CartaoNumero(rotulo: "Chuva média anual dos postos da ANA, 2001–2020",
                                 valor: Fmt.num(estado.media(.ANA, reg), 0), unidade: "mm",
                                 nota: "Média dos postos com dado em cada dia")
                }

                Cartao("Postos da ANA com dado em cada ano",
                       nota: "Postos com pelo menos um dia de dado no ano, segundo o HidroWeb. Os anos mais recentes ainda estão sendo consistidos pela ANA e pelos operadores.") {
                    Chart(barras) { b in
                        BarMark(x: .value("Ano", String(b.ano)), y: .value("Postos", b.postos))
                            .foregroundStyle(Produto.ANA.cor)
                            .cornerRadius(2)
                    }
                    .chartXAxis {
                        AxisMarks(values: rotulos) { _ in
                            AxisValueLabel()
                        }
                    }
                    .frame(height: 200)
                }

                Cartao("Chuva anual: postos da ANA e satélites",
                       nota: "Média aritmética dos postos da ANA na região (pelo menos 3 postos no dia; 9 no Estado) e média areal de cada satélite. Ano com mais de 15 dias sem dado fica em branco.") {
                    if pontos.isEmpty {
                        Text("Sem dados para esta região.").foregroundStyle(.secondary)
                    } else {
                        GraficoLinhas(pontos: pontos, produtos: produtos, unidade: "mm",
                                      ticksX: ticksAnos(anos.min() ?? 1980, anos.max() ?? 2026), altura: 300)
                    }
                }

                Cartao("Estações", nota: "Clique numa estação para ver a série dela. Clique no título de uma coluna para ordenar. O botão Exportar CSV salva a lista filtrada.") {
                    HStack {
                        TextField("Buscar por nome, código, município ou operadora (ex.: Bauru, 02249002, SPÁGUAS)", text: $estado.anaBusca)
                            .textFieldStyle(.roundedBorder)
                            .frame(maxWidth: 460)
                        Text("\(lista.count) postos").foregroundStyle(.secondary).monospacedDigit()
                    }
                    Table(lista, selection: $estado.anaSelecionado, sortOrder: $ordem) {
                        TableColumn("Código", value: \.id).width(min: 76, ideal: 84)
                        TableColumn("Nome", value: \.nome).width(min: 140, ideal: 210)
                        TableColumn("Município", value: \.municipio).width(min: 110, ideal: 140)
                        TableColumn("Operadora", value: \.operadora).width(min: 80, ideal: 100)
                        TableColumn("UGRHI", value: \.sigla).width(min: 70, ideal: 78)
                        TableColumn("Início", value: \.inicio).width(min: 82, ideal: 88)
                        TableColumn("Fim", value: \.fim).width(min: 82, ideal: 88)
                        TableColumn("Anos completos", value: \.anosCompletos) { p in
                            Text(String(p.anosCompletos)).monospacedDigit()
                        }
                        .width(min: 70, ideal: 96)
                        TableColumn("Média anual (mm)", value: \.mediaOrdenavel) { p in
                            Text(Fmt.num(p.mediaAnual, 0)).monospacedDigit()
                        }
                        .width(min: 80, ideal: 110)
                    }
                    .frame(height: 380)
                }

                if let p = estado.anaPostoSelecionado {
                    DetalhePostoAna(posto: p)
                }
            }
        }
    }
}

/// Totais anuais e chuva média por mês do posto escolhido na lista.
struct DetalhePostoAna: View {
    @EnvironmentObject private var estado: EstadoApp
    let posto: AnaPostoDTO

    var body: some View {
        let ano0 = estado.dados.anaResumo?.anoInicial ?? 1980
        let nAnos = estado.dados.anaResumo?.anos ?? 0
        let anual = estado.dados.anaAnual(posto)
        let barrasAno = anual.enumerated().compactMap { k, v in v.isFinite ? BarraValor(x: ano0 + k, y: v) : nil }
        let todosAnos = (0..<max(nAnos, 1)).map { String(ano0 + $0) }
        let rotulosAno = todosAnos.filter { (Int($0) ?? 1) % 5 == 0 }
        let mensal = estado.dados.anaMensal(posto)
        let clima: [BarraValor] = (1...12).compactMap { (mes: Int) -> BarraValor? in
            let v = stride(from: mes - 1, to: mensal.count, by: 12).map { mensal[$0] }.filter(\.isFinite)
            return v.isEmpty ? nil : BarraValor(x: mes, y: v.reduce(0, +) / Double(v.count))
        }
        let operacao = posto.operando ? "em operação" : "desativada"
        let tipo = posto.telemetrica ? "; também tem telemetria" : ""

        Cartao("\(posto.nome) · \(posto.id)",
               nota: "\(posto.municipio), \(posto.sigla). Operadora: \(posto.operadora), \(operacao)\(tipo). Dados de \(dataBR(posto.inicio)) a \(dataBR(posto.fim)); \(posto.anosCompletos) anos completos.") {
            HStack(alignment: .top, spacing: 18) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Total anual (mm)").font(.subheadline).foregroundStyle(.secondary)
                    if barrasAno.isEmpty {
                        Text("Nenhum ano completo (ano com mais de 15 dias sem dado fica em branco).").foregroundStyle(.secondary)
                    } else {
                        Chart(barrasAno) { b in
                            BarMark(x: .value("Ano", String(b.x)), y: .value("mm", b.y))
                                .foregroundStyle(Produto.ANA.cor)
                                .cornerRadius(2)
                        }
                        .chartXScale(domain: todosAnos)
                        .chartXAxis {
                            AxisMarks(values: rotulosAno) { _ in
                                AxisValueLabel()
                            }
                        }
                        .frame(height: 220)
                    }
                }
                .frame(maxWidth: .infinity)
                VStack(alignment: .leading, spacing: 6) {
                    Text("Chuva média por mês (mm), todos os meses com dado").font(.subheadline).foregroundStyle(.secondary)
                    Chart(clima) { b in
                        BarMark(x: .value("Mês", nomesMeses[b.x - 1]), y: .value("mm", b.y))
                            .foregroundStyle(Produto.ANA.cor.opacity(0.8))
                            .cornerRadius(2)
                    }
                    .chartXScale(domain: nomesMeses)
                    .frame(height: 220)
                }
                .frame(maxWidth: 420)
            }
        }
    }
}
