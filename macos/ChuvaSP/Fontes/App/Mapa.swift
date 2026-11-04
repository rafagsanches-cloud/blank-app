import Charts
import SwiftUI

/// Projeção simples lon/lat → tela, com a longitude encurtada por cos(22,5°) (latitude média de SP).
struct Projecao {
    let lonMin: Double, latMax: Double, escala: Double, k: Double, dx: Double, dy: Double

    init(regioes: [Regiao], tamanho: CGSize) {
        let pts = regioes.flatMap { $0.aneis.flatMap { $0 } }
        let lons = pts.map(\.x), lats = pts.map(\.y)
        let lonMin = lons.min() ?? -53.2, lonMax = lons.max() ?? -44.1
        let latMin = lats.min() ?? -25.4, latMax = lats.max() ?? -19.7
        let k = cos(22.5 * .pi / 180)
        let largura = (lonMax - lonMin) * k, altura = latMax - latMin
        let escala = min(Double(tamanho.width) / largura, Double(tamanho.height) / altura)
        self.lonMin = lonMin
        self.latMax = latMax
        self.escala = escala
        self.k = k
        dx = (Double(tamanho.width) - largura * escala) / 2
        dy = (Double(tamanho.height) - altura * escala) / 2
    }

    static func proporcao(_ regioes: [Regiao]) -> CGFloat {
        let pts = regioes.flatMap { $0.aneis.flatMap { $0 } }
        guard let a = pts.map(\.x).min(), let b = pts.map(\.x).max(),
              let c = pts.map(\.y).min(), let d = pts.map(\.y).max(), d > c else { return 1.5 }
        return CGFloat((b - a) * cos(22.5 * .pi / 180) / (d - c))
    }

    func ponto(lon: Double, lat: Double) -> CGPoint {
        CGPoint(x: dx + (lon - lonMin) * k * escala, y: dy + (latMax - lat) * escala)
    }

    func caminho(_ r: Regiao) -> Path {
        var p = Path()
        for anel in r.aneis where anel.count > 2 {
            p.move(to: ponto(lon: anel[0].x, lat: anel[0].y))
            for c in anel.dropFirst() { p.addLine(to: ponto(lon: c.x, lat: c.y)) }
            p.closeSubpath()
        }
        return p
    }
}

struct MapaView: View {
    @EnvironmentObject private var estado: EstadoApp
    @Environment(\.colorScheme) private var esquema

    var body: some View {
        let valores = estado.valoresMapa()
        let vs = valores.values.filter(\.isFinite)
        let escala = EscalaCor(minimo: vs.min() ?? 0, maximo: vs.max() ?? 1,
                               divergente: estado.mapaModo == .tendencia, escuro: esquema == .dark)
        let unidade = estado.mapaModo == .media ? "mm" : "mm/década"

        VStack(alignment: .leading, spacing: 16) {
            CabecalhoRegiao(subtitulo: "Clique numa UGRHI para escolhê-la; clique de novo para voltar ao Estado")
            HStack(spacing: 16) {
                Picker("Produto", selection: $estado.mapaProduto) {
                    ForEach(Produto.satelites) { Text($0.nome).tag($0) }
                }
                .frame(width: 220)
                Picker("Mostrar", selection: $estado.mapaModo) {
                    ForEach(ModoMapa.allCases) { Text($0.titulo).tag($0) }
                }
                .pickerStyle(.segmented)
                .frame(width: 300)
                Toggle("Postos", isOn: $estado.mapaPostos)
                    .toggleStyle(.switch)
            }
            HStack(alignment: .top, spacing: 16) {
                Cartao(estado.mapaModo == .media ? "Chuva média anual, 2001–2020" : "Tendência do total anual (Sen)",
                       nota: estado.mapaModo == .media ? "Média dos totais anuais em cada UGRHI."
                           : "Vermelho: menos chuva; azul: mais chuva. Sen por década sobre toda a série do produto.") {
                    MapaUGRHI(valores: valores, escala: escala, unidade: unidade)
                    LegendaEscala(escala: escala, unidade: unidade)
                }
                .frame(minWidth: 520)
                Cartao("Ranking das UGRHIs", nota: estado.mapaProduto.nome) {
                    RankingUGRHI(valores: valores, escala: escala, unidade: unidade)
                }
                .frame(width: 380)
            }
        }
    }
}

struct Foco: Equatable {
    var sigla: String
    var ponto: CGPoint
}

struct MapaUGRHI: View {
    @EnvironmentObject var estado: EstadoApp
    let valores: [String: Double]
    let escala: EscalaCor
    let unidade: String
    @State var foco: Foco? = nil

    var body: some View {
        let regioes = estado.dados.regioes.filter { !$0.aneis.isEmpty }
        let selecionada = estado.regiao
        let postos = estado.mapaPostos ? estado.dados.postos : []
        GeometryReader { geo in
            let proj = Projecao(regioes: regioes, tamanho: geo.size)
            let formas = regioes.map { r in (sigla: r.sigla, path: proj.caminho(r), cor: escala.cor(valores[r.sigla] ?? .nan)) }
            let pontosPostos = postos.map { proj.ponto(lon: $0.lon, lat: $0.lat) }
            ZStack(alignment: .topLeading) {
                Canvas { ctx, _ in
                    for f in formas {
                        ctx.fill(f.path, with: .color(f.cor), style: FillStyle(eoFill: true))
                        ctx.stroke(f.path, with: .color(Color(nsColor: .windowBackgroundColor)), lineWidth: 0.8)
                    }
                    if let s = formas.first(where: { $0.sigla == selecionada }) {
                        ctx.stroke(s.path, with: .color(.primary), lineWidth: 2.5)
                    }
                    for p in pontosPostos {
                        ctx.fill(Path(ellipseIn: CGRect(x: p.x - 1.6, y: p.y - 1.6, width: 3.2, height: 3.2)),
                                 with: .color(Color.primary.opacity(0.55)))
                    }
                }
                if let f = foco, let r = regioes.first(where: { $0.sigla == f.sigla }) {
                    CaixaDica(titulo: r.rotulo, linhas: [(cor: nil, nome: estado.mapaProduto.nome,
                                                          valor: textoValor(valores[r.sigla]))])
                        .fixedSize()
                        .offset(x: min(f.ponto.x + 14, max(0, geo.size.width - 230)), y: max(0, f.ponto.y - 20))
                        .allowsHitTesting(false)
                }
            }
            .contentShape(Rectangle())
            .onContinuousHover { fase in
                switch fase {
                case let .active(pt):
                    if let s = formas.first(where: { $0.path.contains(pt, eoFill: true) })?.sigla {
                        foco = Foco(sigla: s, ponto: pt)
                    } else {
                        foco = nil
                    }
                case .ended:
                    foco = nil
                }
            }
            .onTapGesture(count: 1) { pt in
                if let s = formas.first(where: { $0.path.contains(pt, eoFill: true) })?.sigla {
                    estado.regiao = estado.regiao == s ? "SP" : s
                }
            }
        }
        .aspectRatio(Projecao.proporcao(regioes), contentMode: .fit)
        .frame(minHeight: 320)
    }

    private func textoValor(_ v: Double?) -> String {
        guard let v, v.isFinite else { return "—" }
        return unidade == "mm" ? Fmt.num(v, 0) + " mm" : Fmt.sinal(v, 1) + " mm/década"
    }
}

struct LegendaEscala: View {
    let escala: EscalaCor
    let unidade: String

    var body: some View {
        let m = max(abs(escala.minimo), abs(escala.maximo))
        let ini = escala.divergente ? -m : escala.minimo
        let fim = escala.divergente ? m : escala.maximo
        VStack(alignment: .leading, spacing: 4) {
            RoundedRectangle(cornerRadius: 3)
                .fill(LinearGradient(colors: escala.paradas, startPoint: .leading, endPoint: .trailing))
                .frame(width: 260, height: 10)
            HStack {
                Text(escala.divergente ? Fmt.sinal(ini, 0) : Fmt.num(ini, 0))
                Spacer()
                Text((escala.divergente ? Fmt.sinal(fim, 0) : Fmt.num(fim, 0)) + " " + unidade)
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            .frame(width: 260)
        }
    }
}

private struct ItemRanking: Identifiable {
    let sigla: String
    let rotulo: String
    let valor: Double
    var id: String { sigla }
}

struct RankingUGRHI: View {
    @EnvironmentObject var estado: EstadoApp
    let valores: [String: Double]
    let escala: EscalaCor
    let unidade: String

    var body: some View {
        let itens = estado.dados.regioes
            .compactMap { r -> ItemRanking? in
                guard let v = valores[r.sigla], v.isFinite else { return nil }
                return ItemRanking(sigla: r.sigla, rotulo: r.rotulo, valor: v)
            }
            .sorted { $0.valor > $1.valor }
        let selecionada = estado.regiao
        Chart(itens) { i in
            BarMark(x: .value(unidade, i.valor), y: .value("UGRHI", i.rotulo))
                .foregroundStyle(escala.cor(i.valor))
                .opacity(selecionada == "SP" || selecionada == i.sigla ? 1 : 0.45)
                .cornerRadius(2)
        }
        .chartYAxis {
            AxisMarks { _ in
                AxisValueLabel()
            }
        }
        .chartXAxis {
            AxisMarks { v in
                AxisGridLine()
                AxisValueLabel {
                    if let x = v.as(Double.self) { Text(Fmt.num(x, 0)) }
                }
            }
        }
        .frame(height: max(300, CGFloat(itens.count) * 22))
    }
}
