import Charts
import SwiftUI

struct ExtremosView: View {
    @EnvironmentObject private var estado: EstadoApp

    var body: some View {
        let reg = estado.regiao
        let par = estado.parametros
        let ind = estado.indice
        let produtos = estado.produtosVisiveis
        let resultados: [ResultadoProduto] = produtos.compactMap { p in
            estado.dados.indices(p, reg, par).map { ResultadoProduto(produto: p, r: $0) }
        }
        let pontos = resultados.flatMap { item in
            pontosEmSegmentos(item.produto, item.r.serie(ind).map { (x: $0.ano, y: $0.valor) })
        }
        let anos = pontos.map(\.x)

        VStack(alignment: .leading, spacing: 18) {
            CabecalhoRegiao(subtitulo: "Índices de extremos de chuva do ETCCDI, calculados como no RClimDex")
            ParametrosIndicesView()
            Cartao("\(ind.nome(nn: par.nn)) (\(ind.unidade))", nota: ind.descricao(nn: par.nn, limiar: par.limiarUmido)) {
                Picker("Índice", selection: $estado.indice) {
                    ForEach(Indice.allCases) { i in
                        Text(i.nome(nn: par.nn)).tag(i)
                    }
                }
                .frame(width: 240)
                if pontos.isEmpty {
                    Text("Sem séries diárias para esta região.").foregroundStyle(.secondary)
                } else {
                    GraficoLinhas(pontos: pontos, produtos: produtos, unidade: ind.unidade,
                                  ticksX: ticksAnos(anos.min() ?? 1980, anos.max() ?? 2026),
                                  casas: ind.unidade == "dias" ? 0 : 1, altura: 300)
                }
            }
            TabelaTendencias(resultados: resultados, indice: ind, nn: par.nn)
            Cartao("Exportar", nota: "Os índices anuais de todos os produtos desta região vão para um CSV. A série diária de um produto pode ser gravada no formato de entrada do RClimDex original.") {
                HStack(spacing: 12) {
                    Button {
                        estado.exportarAbaAtual()
                    } label: {
                        Label("Índices em CSV…", systemImage: "tablecells")
                    }
                    Menu {
                        ForEach(Produto.allCases) { p in
                            Button(p.nome) { estado.exportarRClimDex(p) }
                        }
                    } label: {
                        Label("Série no formato RClimDex…", systemImage: "doc.plaintext")
                    }
                    .fixedSize()
                }
            }
        }
    }
}

struct ParametrosIndicesView: View {
    @EnvironmentObject var estado: EstadoApp

    var body: some View {
        let p = estado.parametros
        Cartao("Parâmetros", nota: "Os padrões são os do RClimDex: período-base 1981–2010, dia úmido com 1 mm ou mais e ano com no máximo 15 dias sem dado. Produtos que começam depois de 2010 usam como base toda a série disponível.") {
            HStack(alignment: .center, spacing: 22) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Período-base").font(.caption).foregroundStyle(.secondary)
                    HStack {
                        Stepper(String(p.baseInicio), value: $estado.parametros.baseInicio, in: 1980...2020)
                        Text("a")
                        Stepper(String(p.baseFim), value: $estado.parametros.baseFim, in: 1985...2026)
                    }
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Dia úmido").font(.caption).foregroundStyle(.secondary)
                    Stepper("\(Fmt.num(p.limiarUmido, 1)) mm", value: $estado.parametros.limiarUmido, in: 0.1...10, step: 0.1)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("Limiar do Rnnmm").font(.caption).foregroundStyle(.secondary)
                    Stepper("\(Fmt.num(p.nn, 0)) mm", value: $estado.parametros.nn, in: 5...300, step: 5)
                }
                Toggle("CDD e CWD atravessam o ano", isOn: $estado.parametros.sequenciasCruzamAnos)
                Spacer()
                Button("Padrão do RClimDex") { estado.parametros = ParametrosIndices() }
                    .disabled(p == ParametrosIndices())
            }
        }
    }
}

struct ResultadoProduto: Identifiable {
    let produto: Produto
    let r: ResultadoIndices
    var id: String { produto.rawValue }
}

struct TabelaTendencias: View {
    let resultados: [ResultadoProduto]
    let indice: Indice
    let nn: Double

    var body: some View {
        Cartao("Tendências de \(indice.nome(nn: nn))",
               nota: "Sen e regressão linear por década; p do teste de Mann-Kendall e da regressão. ● marca p < 0,05 no Mann-Kendall. P95 e P99 são os limiares dos dias muito e extremamente úmidos no período-base usado.") {
            Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 8) {
                GridRow {
                    ForEach(["Produto", "Período", "Anos", "Sen/década", "p (MK)", "Linear/década", "p (linear)", "P95", "P99", "Base"], id: \.self) { c in
                        Text(c).fontWeight(.medium)
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
                Divider().gridCellUnsizedAxes(.horizontal)
                ForEach(resultados) { item in
                    let t = tendencia(anos: item.r.anos, valores: item.r.valores[indice] ?? [])
                    GridRow {
                        HStack(spacing: 6) {
                            Circle().fill(item.produto.cor).frame(width: 8, height: 8)
                            Text(item.produto.nome)
                        }
                        Text(t.map { "\($0.anoInicio)–\($0.anoFim)" } ?? "—").foregroundStyle(.secondary)
                        Text(t.map { String($0.n) } ?? "—")
                        Text(Fmt.sinal(t?.senPorDecada, 2))
                        Text((t?.significativa ?? false ? "● " : "") + Fmt.p(t?.mkP))
                        Text(Fmt.sinal(t?.olsPorDecada, 2))
                        Text(Fmt.p(t?.pOLS))
                        Text(Fmt.num(item.r.p95, 1) + " mm")
                        Text(Fmt.num(item.r.p99, 1) + " mm")
                        Text("\(String(item.r.baseUsada.lowerBound))–\(String(item.r.baseUsada.upperBound))").foregroundStyle(.secondary)
                    }
                    .monospacedDigit()
                }
            }
            .font(.callout)
        }
    }
}
