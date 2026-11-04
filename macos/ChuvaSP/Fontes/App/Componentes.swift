import Charts
import SwiftUI

// MARK: - Cartões

struct Cartao<Conteudo: View>: View {
    let titulo: String
    var nota: String?
    let conteudo: Conteudo

    init(_ titulo: String, nota: String? = nil, @ViewBuilder conteudo: () -> Conteudo) {
        self.titulo = titulo
        self.nota = nota
        self.conteudo = conteudo()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(titulo).font(.headline)
            if let nota {
                Text(nota).font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            conteudo
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Color(nsColor: .controlBackgroundColor)))
        .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Color(nsColor: .separatorColor), lineWidth: 1))
    }
}

struct CartaoNumero: View {
    let rotulo: String
    let valor: String
    let unidade: String
    let nota: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(rotulo).font(.callout).foregroundStyle(.secondary).lineLimit(2)
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(valor).font(.system(size: 30, weight: .regular, design: .serif)).monospacedDigit()
                Text(unidade).font(.callout).foregroundStyle(.secondary)
            }
            Text(nota).font(.caption).foregroundStyle(.secondary).lineLimit(2)
        }
        .padding(16)
        .frame(maxWidth: .infinity, minHeight: 124, alignment: .topLeading)
        .background(RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Color(nsColor: .controlBackgroundColor)))
        .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Color(nsColor: .separatorColor), lineWidth: 1))
    }
}

struct CaixaDica: View {
    let titulo: String
    let linhas: [(cor: Color?, nome: String, valor: String)]

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(titulo).font(.caption).foregroundStyle(.secondary)
            ForEach(Array(linhas.enumerated()), id: \.offset) { _, l in
                HStack(spacing: 6) {
                    if let c = l.cor { Circle().fill(c).frame(width: 8, height: 8) }
                    Text(l.nome).font(.caption)
                    Spacer(minLength: 12)
                    Text(l.valor).font(.caption).monospacedDigit()
                }
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .frame(minWidth: 150)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 8, style: .continuous).strokeBorder(Color(nsColor: .separatorColor)))
    }
}

// MARK: - Gráfico de linhas com x inteiro (ano, mês ou dia)

struct PontoLinha: Identifiable {
    let produto: Produto
    let x: Int
    let y: Double
    let segmento: Int
    let isolado: Bool
    var id: String { "\(produto.rawValue)-\(x)" }
}

/// Quebra a linha onde há falta (NaN) ou salto maior que `passo` em x.
func pontosEmSegmentos(_ produto: Produto, _ serie: [(x: Int, y: Double)], passo: Int = 1) -> [PontoLinha] {
    var grupos = [[(x: Int, y: Double)]]()
    var atual = [(x: Int, y: Double)]()
    var ultimoX: Int?
    for p in serie.sorted(by: { $0.x < $1.x }) {
        if !p.y.isFinite {
            if !atual.isEmpty { grupos.append(atual); atual = [] }
            ultimoX = nil
            continue
        }
        if let u = ultimoX, p.x - u > passo, !atual.isEmpty { grupos.append(atual); atual = [] }
        atual.append(p)
        ultimoX = p.x
    }
    if !atual.isEmpty { grupos.append(atual) }
    var out = [PontoLinha]()
    for (k, g) in grupos.enumerated() {
        for p in g { out.append(PontoLinha(produto: produto, x: p.x, y: p.y, segmento: k, isolado: g.count == 1)) }
    }
    return out
}

struct GraficoLinhas: View {
    let pontos: [PontoLinha]
    let produtos: [Produto]
    let unidade: String
    let ticksX: [Int]
    var rotuloX: (Int) -> String = { String($0) }
    var rotuloDica: ((Int) -> String)?
    var casas = 0
    var incluirZero = false
    var altura: CGFloat = 300

    @State var selecionado: Int? = nil

    private var produtosComDado: [Produto] {
        let tem = Set(pontos.map(\.produto))
        return produtos.filter { tem.contains($0) }
    }

    private func linhasDica(_ x: Int) -> [(cor: Color?, nome: String, valor: String)] {
        pontos.filter { $0.x == x }
            .sorted { $0.y > $1.y }
            .map { (cor: Optional($0.produto.cor), nome: $0.produto.nome, valor: Fmt.num($0.y, casas) + " " + unidade) }
    }

    var body: some View {
        let lista = produtosComDado
        let xs = pontos.map(\.x)
        let xMin = min(ticksX.first ?? 0, xs.min() ?? 0)
        let xMax = max(ticksX.last ?? 1, xs.max() ?? 1, xMin + 1)
        Chart {
            ForEach(pontos) { p in
                LineMark(x: .value("x", p.x), y: .value(unidade, p.y), series: .value("Série", "\(p.produto.rawValue)-\(p.segmento)"))
                    .foregroundStyle(by: .value("Produto", p.produto.nome))
                    .lineStyle(StrokeStyle(lineWidth: p.produto == .POSTOS ? 2.6 : 1.8, lineCap: .round, lineJoin: .round))
                if p.isolado {
                    PointMark(x: .value("x", p.x), y: .value(unidade, p.y))
                        .foregroundStyle(by: .value("Produto", p.produto.nome))
                        .symbolSize(18)
                }
            }
            if let s = selecionado {
                RuleMark(x: .value("x", s))
                    .foregroundStyle(Color.secondary.opacity(0.4))
                    .annotation(position: .top, spacing: 2, overflowResolution: .init(x: .fit(to: .chart), y: .disabled)) {
                        CaixaDica(titulo: (rotuloDica ?? rotuloX)(s), linhas: linhasDica(s))
                    }
            }
        }
        .chartForegroundStyleScale(domain: lista.map(\.nome), range: lista.map(\.cor))
        .chartXSelection(value: $selecionado)
        .chartXScale(domain: xMin...xMax, range: .plotDimension(startPadding: 4, endPadding: 16))
        .chartYScale(domain: .automatic(includesZero: incluirZero))
        .chartXAxis {
            AxisMarks(values: ticksX) { v in
                AxisGridLine()
                AxisTick()
                AxisValueLabel {
                    if let x = v.as(Int.self) { Text(rotuloX(x)) }
                }
            }
        }
        .chartYAxis {
            AxisMarks(position: .leading) { v in
                AxisGridLine()
                AxisValueLabel {
                    if let y = v.as(Double.self) { Text(Fmt.num(y, abs(y) >= 10 || y == y.rounded() ? 0 : 1)) }
                }
            }
        }
        .chartLegend(position: .bottom, alignment: .leading)
        .frame(height: altura)
    }
}

/// Marcas de anos a cada `passo` anos dentro do intervalo.
func ticksAnos(_ a0: Int, _ a1: Int) -> [Int] {
    let span = a1 - a0
    let passo = span > 30 ? 5 : (span > 12 ? 2 : 1)
    let ini = Int((Double(a0) / Double(passo)).rounded(.up)) * passo
    return Array(stride(from: ini, through: a1, by: passo))
}

// MARK: - Escala de cores do mapa

struct EscalaCor {
    let minimo: Double
    let maximo: Double
    let divergente: Bool
    let escuro: Bool

    private struct RGB { var r: Double; var g: Double; var b: Double }

    private static func rgb(_ hex: UInt32) -> RGB {
        RGB(r: Double((hex >> 16) & 0xFF) / 255, g: Double((hex >> 8) & 0xFF) / 255, b: Double(hex & 0xFF) / 255)
    }

    private static func misturar(_ a: RGB, _ b: RGB, _ t: Double) -> Color {
        let u = min(max(t, 0), 1)
        return Color(.sRGB, red: a.r + (b.r - a.r) * u, green: a.g + (b.g - a.g) * u, blue: a.b + (b.b - a.b) * u, opacity: 1)
    }

    func cor(_ v: Double) -> Color {
        guard v.isFinite else { return Color.gray.opacity(0.25) }
        if divergente {
            let m = max(abs(minimo), abs(maximo), 1e-9)
            let meio = EscalaCor.rgb(escuro ? 0x383835 : 0xF0EFEC)
            let azul = EscalaCor.rgb(escuro ? 0x5598E7 : 0x2A78D6)
            let vermelho = EscalaCor.rgb(escuro ? 0xE66767 : 0xD03B3B)
            return v < 0 ? EscalaCor.misturar(meio, vermelho, -v / m) : EscalaCor.misturar(meio, azul, v / m)
        }
        let t = maximo > minimo ? (v - minimo) / (maximo - minimo) : 0.5
        let claro = EscalaCor.rgb(escuro ? 0x1C3550 : 0xCDE2FB)
        let forte = EscalaCor.rgb(escuro ? 0x86B6EF : 0x104281)
        return EscalaCor.misturar(claro, forte, t)
    }

    var paradas: [Color] {
        (0...10).map { k in
            let t = Double(k) / 10
            if divergente {
                let m = max(abs(minimo), abs(maximo))
                return cor(-m + 2 * m * t)
            }
            return cor(minimo + (maximo - minimo) * t)
        }
    }
}
