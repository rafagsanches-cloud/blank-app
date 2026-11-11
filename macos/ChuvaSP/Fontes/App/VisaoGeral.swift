import Charts
import SwiftUI

struct VisaoGeralView: View {
    @EnvironmentObject private var estado: EstadoApp

    var body: some View {
        let reg = estado.regiao
        let produtos = estado.produtosVisiveis
        let pontos = produtos.flatMap { p in
            pontosEmSegmentos(p, estado.serieAnual(p, reg).map { (x: $0.ano, y: $0.mm) })
        }
        let anos = pontos.map(\.x)
        let tChirps = estado.tendenciaAnual(.CHIRPS, reg)
        let rChirps = estado.medianaValidacao(.CHIRPS, reg, .rDiario)
        let rMensal = estado.medianaValidacao(.CHIRPS, reg, .rMensal)

        VStack(alignment: .leading, spacing: 18) {
            CabecalhoRegiao(subtitulo: "Chuva por satélite e postos pluviométricos")

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 12)], spacing: 12) {
                CartaoNumero(rotulo: "Chuva média anual, CHIRPS, 2001–2020",
                             valor: Fmt.num(estado.media(.CHIRPS, reg), 0), unidade: "mm",
                             nota: "Média dos totais anuais")
                CartaoNumero(rotulo: "Tendência do total anual, CHIRPS",
                             valor: Fmt.sinal(tChirps?.senPorDecada, 1), unidade: "mm por década",
                             nota: tChirps.map { "Sen; Mann-Kendall p = \(Fmt.p($0.mkP)), \($0.anoInicio)–\($0.anoFim)" } ?? "—")
                CartaoNumero(rotulo: "Postos pluviométricos com dados desde 1980",
                             valor: Fmt.num(Double(estado.postosNaRegiao(reg).count), 0), unidade: "postos",
                             nota: "Rede da ANA e do DAEE, via GHCN-Daily")
                CartaoNumero(rotulo: "Correlação diária CHIRPS × postos (mediana)",
                             valor: Fmt.num(rChirps?.valor, 2), unidade: "",
                             nota: "Mensal: \(Fmt.num(rMensal?.valor, 2)) · \(rChirps?.postos ?? 0) postos")
            }

            Cartao("Chuva anual por produto",
                   nota: "Total do ano civil (mm). Ano com mais de 15 dias sem dado fica em branco. Passe o cursor para ver os valores; use o botão Produtos para esconder séries.") {
                if pontos.isEmpty {
                    Text("Sem dados para esta região.").foregroundStyle(.secondary)
                } else {
                    GraficoLinhas(pontos: pontos, produtos: produtos, unidade: "mm",
                                  ticksX: ticksAnos(anos.min() ?? 1980, anos.max() ?? 2026), altura: 320)
                }
            }

            HStack(alignment: .top, spacing: 12) {
                Cartao("Chuva média por mês", nota: "Satélites e postos da ANA: 2001–2020. Postos (média): 1980–1999, quando a rede do GHCN tinha mais postos ativos.") {
                    let meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
                    let clima = produtos.flatMap { p -> [PontoLinha] in
                        let c = estado.climatologia(p, reg)
                        return pontosEmSegmentos(p, c.enumerated().map { (x: $0.offset + 1, y: $0.element) })
                    }
                    GraficoLinhas(pontos: clima, produtos: produtos, unidade: "mm", ticksX: Array(1...12),
                                  rotuloX: { meses[$0 - 1] }, incluirZero: true, altura: 260)
                }
                Cartao("Tendência do total anual", nota: "Estimador de Sen por década; p do teste de Mann-Kendall. ● marca p < 0,05.") {
                    Grid(alignment: .leading, horizontalSpacing: 14, verticalSpacing: 8) {
                        GridRow {
                            Text("Produto").fontWeight(.medium)
                            Text("Período").fontWeight(.medium)
                            Text("Sen").fontWeight(.medium).gridColumnAlignment(.trailing)
                            Text("p").fontWeight(.medium).gridColumnAlignment(.trailing)
                        }
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        Divider().gridCellUnsizedAxes(.horizontal)
                        ForEach(Produto.allCases) { p in
                            let t = estado.tendenciaAnual(p, reg)
                            GridRow {
                                HStack(spacing: 6) {
                                    Circle().fill(p.cor).frame(width: 8, height: 8)
                                    Text(p.nome)
                                }
                                Text(verbatim: t.map { "\(String($0.anoInicio))–\(String($0.anoFim))" } ?? "—").foregroundStyle(.secondary)
                                Text(Fmt.sinal(t?.senPorDecada, 1)).monospacedDigit()
                                Text((t?.significativa ?? false ? "● " : "") + Fmt.p(t?.mkP)).monospacedDigit()
                            }
                        }
                    }
                    .font(.callout)
                }
                .frame(maxWidth: 420)
            }
        }
    }
}
