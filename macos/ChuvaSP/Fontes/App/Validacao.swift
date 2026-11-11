import Charts
import SwiftUI

struct PontoValidacao: Identifiable {
    let id: String
    let produto: Produto
    let x: Double
    let y: Double
}

struct MedianaValidacao: Identifiable {
    let produto: Produto
    let posicao: Double
    let valor: Double
    var id: String { produto.rawValue }
}

/// Espalhamento horizontal fixo para cada posto (o mesmo a cada abertura).
private func espalhamento(_ texto: String) -> Double {
    var h: UInt64 = 5381
    for b in texto.utf8 { h = (h &* 33) &+ UInt64(b) }
    return Double(h % 1000) / 1000 - 0.5
}

struct ValidacaoView: View {
    @EnvironmentObject private var estado: EstadoApp

    var body: some View {
        let reg = estado.regiao
        let metrica = estado.metrica
        let fonte = estado.fonteValidacao
        let lista = estado.validacoes(reg, fonte: fonte)
        let produtos = Produto.satelites.filter { p in lista.contains { $0.produto == p.rawValue } }
        var pontos = [PontoValidacao]()
        var medianas = [MedianaValidacao]()
        for (i, p) in produtos.enumerated() {
            let vs = lista.filter { $0.produto == p.rawValue }
            for v in vs {
                if let y = metrica.valor(v), y.isFinite {
                    pontos.append(PontoValidacao(id: v.id, produto: p, x: Double(i) + 0.62 * espalhamento(v.estacao), y: y))
                }
            }
            let m = mediana(vs.compactMap { metrica.valor($0) })
            if m.isFinite { medianas.append(MedianaValidacao(produto: p, posicao: Double(i), valor: m)) }
        }
        let ys = pontos.map(\.y).sorted()
        let baixo = ys.isEmpty ? 0 : ys[Int(Double(ys.count - 1) * 0.01)]
        let alto = ys.isEmpty ? 1 : ys[Int(Double(ys.count - 1) * 0.995)]
        let folga = max((alto - baixo) * 0.05, 0.01)
        let dominioY = (min(baixo, metrica == .viesPct ? 0 : baixo) - folga)...(alto + folga)

        return VStack(alignment: .leading, spacing: 18) {
            CabecalhoRegiao(subtitulo: "Cada posto comparado com o pixel do satélite que o contém")
            if !estado.dados.anaValidacao.isEmpty {
                Picker("Comparar com", selection: $estado.fonteValidacao) {
                    ForEach(FonteValidacao.allCases) { Text($0.titulo).tag($0) }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 520)
            }
            Cartao("Distribuição entre os postos",
                   nota: fonte == .ghcn
                       ? "Um ponto por posto; o traço marca a mediana. IMERG e CMORPH começam em 1998, depois da maior parte das séries de postos, e por isso têm poucos postos em comum."
                       : "Um ponto por posto da ANA com pelo menos um ano em comum com o satélite; o traço marca a mediana. As séries da ANA seguem pelos anos 2000, então IMERG e CMORPH têm bem mais postos para comparar.") {
                Picker("Métrica", selection: $estado.metrica) {
                    ForEach(Metrica.allCases) { Text($0.titulo).tag($0) }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 460)
                if pontos.isEmpty {
                    Text("Nenhum posto desta região tem dados no mesmo período dos satélites.").foregroundStyle(.secondary)
                } else {
                    Chart {
                        ForEach(pontos) { p in
                            PointMark(x: .value("Produto", p.x), y: .value(metrica.titulo, p.y))
                                .foregroundStyle(p.produto.cor.opacity(pontos.count > 600 ? 0.35 : 0.6))
                                .symbolSize(14)
                        }
                        ForEach(medianas) { m in
                            RuleMark(xStart: .value("Produto", m.posicao - 0.38), xEnd: .value("Produto", m.posicao + 0.38),
                                     y: .value("Mediana", m.valor))
                                .foregroundStyle(Color.primary)
                                .lineStyle(StrokeStyle(lineWidth: 3, lineCap: .round))
                        }
                    }
                    .chartXScale(domain: -0.6...(Double(produtos.count) - 0.4))
                    .chartYScale(domain: dominioY)
                    .chartPlotStyle { $0.clipped() }
                    .chartXAxis {
                        AxisMarks(values: produtos.indices.map { Double($0) }) { v in
                            AxisValueLabel {
                                if let d = v.as(Double.self), produtos.indices.contains(Int(d.rounded())) {
                                    Text(produtos[Int(d.rounded())].nome)
                                }
                            }
                        }
                    }
                    .frame(height: 320)
                }
            }
            Cartao("Mediana entre os postos", nota: "Viés: diferença percentual do total do satélite em relação ao posto. KGE: eficiência de Kling-Gupta. CSI: acerto dos dias com chuva (limiar de 1 mm).") {
                Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 8) {
                    GridRow {
                        ForEach(["Produto", "Postos", "r diário", "r mensal", "Viés (%)", "KGE", "CSI"], id: \.self) { c in
                            Text(c).fontWeight(.medium)
                        }
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    Divider().gridCellUnsizedAxes(.horizontal)
                    ForEach(produtos) { p in
                        GridRow {
                            HStack(spacing: 6) {
                                Circle().fill(p.cor).frame(width: 8, height: 8)
                                Text(p.nome)
                            }
                            Text(String(estado.medianaValidacao(p, reg, .rDiario, fonte: fonte)?.postos ?? 0))
                            Text(Fmt.num(estado.medianaValidacao(p, reg, .rDiario, fonte: fonte)?.valor, 2))
                            Text(Fmt.num(estado.medianaValidacao(p, reg, .rMensal, fonte: fonte)?.valor, 2))
                            Text(Fmt.sinal(estado.medianaValidacao(p, reg, .viesPct, fonte: fonte)?.valor, 1))
                            Text(Fmt.num(estado.medianaValidacao(p, reg, .kge, fonte: fonte)?.valor, 2))
                            Text(Fmt.num(estado.medianaValidacao(p, reg, .csi, fonte: fonte)?.valor, 2))
                        }
                        .monospacedDigit()
                    }
                }
                .font(.callout)
            }
        }
    }
}
