// Cálculos do ClimdexSP em Swift: índices ETCCDI de precipitação, tendências
// (Sen, Mann-Kendall e regressão linear) e utilidades de datas.
// Mesmas definições do R/ClimdexSP.R; os testes em Testes/main.swift comparam
// os resultados com valores gerados pelo programa em R.

import Foundation

// MARK: - Datas civis (calendário gregoriano, sem fuso)

struct DataCivil: Hashable, Comparable, CustomStringConvertible {
    var ano: Int
    var mes: Int
    var dia: Int

    static func < (a: DataCivil, b: DataCivil) -> Bool { a.numeroDoDia < b.numeroDoDia }

    /// Dias desde 1970-01-01 (algoritmo de H. Hinnant).
    var numeroDoDia: Int {
        let y = mes <= 2 ? ano - 1 : ano
        let era = (y >= 0 ? y : y - 399) / 400
        let yoe = y - era * 400
        let mp = (mes + 9) % 12
        let doy = (153 * mp + 2) / 5 + dia - 1
        let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy
        return era * 146097 + doe - 719468
    }

    init(ano: Int, mes: Int, dia: Int) {
        self.ano = ano
        self.mes = mes
        self.dia = dia
    }

    init(numeroDoDia z0: Int) {
        let z = z0 + 719468
        let era = (z >= 0 ? z : z - 146096) / 146097
        let doe = z - era * 146097
        let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365
        let doy = doe - (365 * yoe + yoe / 4 - yoe / 100)
        let mp = (5 * doy + 2) / 153
        let d = doy - (153 * mp + 2) / 5 + 1
        let m = mp < 10 ? mp + 3 : mp - 9
        self.init(ano: yoe + era * 400 + (m <= 2 ? 1 : 0), mes: m, dia: d)
    }

    /// Lê "AAAA-MM-DD" ou "AAAA-MM".
    init?(texto: String) {
        let p = texto.split(separator: "-").compactMap { Int($0) }
        guard p.count >= 2 else { return nil }
        self.init(ano: p[0], mes: p[1], dia: p.count > 2 ? p[2] : 1)
    }

    var description: String { String(format: "%04d-%02d-%02d", ano, mes, dia) }
}

// MARK: - Série diária

struct SerieDiaria {
    let produto: String
    let sigla: String
    let inicio: DataCivil
    /// mm por dia; NaN = falta
    let valores: [Double]

    var fim: DataCivil { DataCivil(numeroDoDia: inicio.numeroDoDia + valores.count - 1) }

    /// Completa o calendário de 1º de janeiro do primeiro ano a 31 de dezembro do último (faltas = NaN).
    func calendarioCompleto() -> (inicio: DataCivil, valores: [Double], anos: [Int], meses: [Int]) {
        let ini = DataCivil(ano: inicio.ano, mes: 1, dia: 1)
        let fimAno = DataCivil(ano: fim.ano, mes: 12, dia: 31)
        let n = fimAno.numeroDoDia - ini.numeroDoDia + 1
        var x = [Double](repeating: .nan, count: n)
        let desloc = inicio.numeroDoDia - ini.numeroDoDia
        for (i, v) in valores.enumerated() { x[desloc + i] = v }
        var anos = [Int](repeating: 0, count: n)
        var meses = [Int](repeating: 0, count: n)
        let base = ini.numeroDoDia
        for i in 0..<n {
            let d = DataCivil(numeroDoDia: base + i)
            anos[i] = d.ano
            meses[i] = d.mes
        }
        return (ini, x, anos, meses)
    }
}

// MARK: - Índices ETCCDI

enum Indice: String, CaseIterable, Identifiable {
    case PRCPTOT, SDII, R10mm, R20mm, Rnnmm, CDD, CWD, R95p, R99p, R95pTOT, R99pTOT, Rx1day, Rx5day

    var id: String { rawValue }

    func nome(nn: Double) -> String {
        self == .Rnnmm ? "R\(Int(nn.rounded()))mm" : rawValue
    }

    func descricao(nn: Double, limiar: Double) -> String {
        let l = Fmt.num(limiar, limiar.rounded() == limiar ? 0 : 1)
        switch self {
        case .PRCPTOT: return "Chuva total do ano nos dias com pelo menos \(l) mm."
        case .SDII: return "Chuva dos dias úmidos dividida pelo número de dias úmidos."
        case .R10mm: return "Dias no ano com chuva de 10 mm ou mais."
        case .R20mm: return "Dias no ano com chuva de 20 mm ou mais."
        case .Rnnmm: return "Dias no ano com chuva de \(Fmt.num(nn, 0)) mm ou mais."
        case .CDD: return "Maior sequência de dias com menos de \(l) mm."
        case .CWD: return "Maior sequência de dias com pelo menos \(l) mm."
        case .R95p: return "Chuva do ano nos dias acima do percentil 95 dos dias úmidos do período-base."
        case .R99p: return "Chuva do ano nos dias acima do percentil 99 dos dias úmidos do período-base."
        case .R95pTOT: return "Parcela da chuva anual que caiu em dias acima do percentil 95."
        case .R99pTOT: return "Parcela da chuva anual que caiu em dias acima do percentil 99."
        case .Rx1day: return "Maior chuva em um único dia do ano."
        case .Rx5day: return "Maior soma de chuva em 5 dias seguidos."
        }
    }

    var unidade: String {
        switch self {
        case .PRCPTOT, .R95p, .R99p, .Rx1day, .Rx5day: return "mm"
        case .SDII: return "mm/dia"
        case .R95pTOT, .R99pTOT: return "%"
        default: return "dias"
        }
    }
}

struct ParametrosIndices: Hashable {
    var baseInicio = 1981
    var baseFim = 2010
    var limiarUmido = 1.0
    var nn = 50.0
    var sequenciasCruzamAnos = true
    var maxFaltasAno = 15
}

struct ResultadoIndices {
    let anos: [Int]
    let valores: [Indice: [Double]]
    let p95: Double
    let p99: Double
    let baseUsada: ClosedRange<Int>
    let faltasPorAno: [Int]

    func serie(_ i: Indice) -> [(ano: Int, valor: Double)] {
        zip(anos, valores[i] ?? []).map { ($0, $1) }
    }
}

/// Quantil tipo 8 de Hyndman & Fan, reproduzindo exatamente stats::quantile(type = 8) do R
/// (a mesma folga numérica e a mesma ordem das contas), como no climdex.pcic.
func quantilTipo8(_ ordenados: [Double], _ p: Double) -> Double {
    let n = ordenados.count
    guard n > 0 else { return .nan }
    let a = 1.0 / 3.0, b = 1.0 / 3.0
    let folga = 4 * Double.ulpOfOne
    let nppm = a + p * (Double(n) + 1 - a - b)
    let j = Int(floor(nppm + folga))
    var h = nppm - Double(j)
    if abs(h) < folga { h = 0 }
    // vetor estendido do R: x[1], x[1], x..., x[n], x[n]; posições j+2 e j+3 (base 1)
    func estendido(_ k: Int) -> Double {
        let i = k - 2  // índice base 1 no vetor original
        return ordenados[min(max(i, 1), n) - 1]
    }
    let xlo = estendido(j + 2), xhi = estendido(j + 3)
    if h == 1 { return xhi }
    if h > 0 && h < 1 && xlo != xhi { return (1 - h) * xlo + h * xhi }
    return xlo
}

func calcularIndices(_ serie: SerieDiaria, _ p: ParametrosIndices) -> ResultadoIndices {
    let c = serie.calendarioCompleto()
    let x = c.valores
    let ano = c.anos
    let n = x.count
    let anos = Array(Set(ano)).sorted()
    var posAno = [Int: Int]()
    for (i, a) in anos.enumerated() { posAno[a] = i }
    let nA = anos.count

    // percentis dos dias úmidos do período-base
    let bIni = min(p.baseInicio, p.baseFim), bFim = max(p.baseInicio, p.baseFim)
    var umidosBase = [Double]()
    for i in 0..<n where x[i].isFinite && x[i] >= p.limiarUmido && ano[i] >= bIni && ano[i] <= bFim {
        umidosBase.append(x[i])
    }
    var baseUsada = bIni...bFim
    if umidosBase.count < 100 {
        umidosBase = x.filter { $0.isFinite && $0 >= p.limiarUmido }
        let anosComDado = (0..<n).filter { x[$0].isFinite }.map { ano[$0] }
        if let a = anosComDado.min(), let b = anosComDado.max() { baseUsada = a...b }
    }
    umidosBase.sort()
    let p95 = quantilTipo8(umidosBase, 0.95)
    let p99 = quantilTipo8(umidosBase, 0.99)

    var faltas = [Int](repeating: 0, count: nA)
    var comDado = [Int](repeating: 0, count: nA)
    var prcptot = [Double](repeating: 0, count: nA)
    var nUmidos = [Int](repeating: 0, count: nA)
    var r10 = [Double](repeating: 0, count: nA)
    var r20 = [Double](repeating: 0, count: nA)
    var rnn = [Double](repeating: 0, count: nA)
    var r95 = [Double](repeating: 0, count: nA)
    var r99 = [Double](repeating: 0, count: nA)
    var rx1 = [Double](repeating: -.infinity, count: nA)
    var rx5 = [Double](repeating: -.infinity, count: nA)

    for i in 0..<n {
        let k = posAno[ano[i]]!
        let v = x[i]
        if !v.isFinite { faltas[k] += 1 } else {
            comDado[k] += 1
            if v >= p.limiarUmido {
                prcptot[k] += v
                nUmidos[k] += 1
                if v > p95 { r95[k] += v }
                if v > p99 { r99[k] += v }
            }
            if v >= 10 { r10[k] += 1 }
            if v >= 20 { r20[k] += 1 }
            if v >= p.nn { rnn[k] += 1 }
            if v > rx1[k] { rx1[k] = v }
        }
        // soma de 5 dias terminando no dia i (falta se algum dos 5 faltar)
        if i >= 4 {
            var s = 0.0
            var ok = true
            for j in (i - 4)...i {
                if x[j].isFinite { s += x[j] } else { ok = false; break }
            }
            if ok && s > rx5[k] { rx5[k] = s }
        }
    }

    // sequências secas e úmidas
    func maiorSequencia(_ cond: (Double) -> Bool) -> [Double] {
        var res = [Double](repeating: 0, count: nA)
        var corrida = 0
        for i in 0..<n {
            let v = x[i]
            let ok = v.isFinite && cond(v)
            if p.sequenciasCruzamAnos {
                corrida = ok ? corrida + 1 : 0
                let terminou = ok && (i == n - 1 || !(x[i + 1].isFinite && cond(x[i + 1])))
                if terminou {
                    let k = posAno[ano[i]]!
                    res[k] = max(res[k], Double(corrida))
                }
            } else {
                if i > 0 && ano[i] != ano[i - 1] { corrida = 0 }
                corrida = ok ? corrida + 1 : 0
                let k = posAno[ano[i]]!
                res[k] = max(res[k], Double(corrida))
            }
        }
        return res
    }
    let limiar = p.limiarUmido
    let cdd = maiorSequencia { $0 < limiar }
    let cwd = maiorSequencia { $0 >= limiar }

    var valores = [Indice: [Double]]()
    for i in Indice.allCases { valores[i] = [Double](repeating: .nan, count: nA) }
    for k in 0..<nA {
        let ok = faltas[k] <= p.maxFaltasAno && comDado[k] > 0
        guard ok else { continue }
        valores[.PRCPTOT]![k] = prcptot[k]
        valores[.SDII]![k] = nUmidos[k] > 0 ? prcptot[k] / Double(nUmidos[k]) : 0
        valores[.R10mm]![k] = r10[k]
        valores[.R20mm]![k] = r20[k]
        valores[.Rnnmm]![k] = rnn[k]
        valores[.CDD]![k] = cdd[k]
        valores[.CWD]![k] = cwd[k]
        valores[.R95p]![k] = r95[k]
        valores[.R99p]![k] = r99[k]
        valores[.R95pTOT]![k] = prcptot[k] > 0 ? 100 * r95[k] / prcptot[k] : .nan
        valores[.R99pTOT]![k] = prcptot[k] > 0 ? 100 * r99[k] / prcptot[k] : .nan
        valores[.Rx1day]![k] = rx1[k].isFinite ? rx1[k] : .nan
        valores[.Rx5day]![k] = rx5[k].isFinite ? rx5[k] : .nan
    }
    return ResultadoIndices(anos: anos, valores: valores, p95: p95, p99: p99, baseUsada: baseUsada, faltasPorAno: faltas)
}

// MARK: - Tendências

struct Tendencia {
    let n: Int
    let anoInicio: Int
    let anoFim: Int
    let senPorDecada: Double
    let olsPorDecada: Double
    let erroPadraoPorDecada: Double
    let pOLS: Double
    let mkTau: Double
    let mkP: Double

    var significativa: Bool { mkP < 0.05 }
}

func mediana(_ v: [Double]) -> Double {
    let s = v.filter { $0.isFinite }.sorted()
    guard !s.isEmpty else { return .nan }
    let m = s.count / 2
    return s.count % 2 == 1 ? s[m] : (s[m - 1] + s[m]) / 2
}

/// Distribuição normal padrão acumulada.
func normalAcumulada(_ z: Double) -> Double { 0.5 * erfc(-z / 2.0.squareRoot()) }

/// Função beta incompleta regularizada I_x(a, b) (fração continuada de Lentz).
func betaIncompleta(_ a: Double, _ b: Double, _ x: Double) -> Double {
    if x <= 0 { return 0 }
    if x >= 1 { return 1 }
    let lbeta = lgamma(a + b) - lgamma(a) - lgamma(b)
    let frente = exp(log(x) * a + log(1 - x) * b + lbeta)
    if x < (a + 1) / (a + b + 2) {
        return frente * fracaoContinuaBeta(a, b, x) / a
    }
    return 1 - frente * fracaoContinuaBeta(b, a, 1 - x) / b
}

private func fracaoContinuaBeta(_ a: Double, _ b: Double, _ x: Double) -> Double {
    let minimo = 1e-300
    let qab = a + b, qap = a + 1, qam = a - 1
    var c = 1.0
    var d = 1 - qab * x / qap
    if abs(d) < minimo { d = minimo }
    d = 1 / d
    var h = d
    for m in 1...500 {
        let md = Double(m), m2 = 2 * md
        var aa = md * (b - md) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        if abs(d) < minimo { d = minimo }
        c = 1 + aa / c
        if abs(c) < minimo { c = minimo }
        d = 1 / d
        h *= d * c
        aa = -(a + md) * (qab + md) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        if abs(d) < minimo { d = minimo }
        c = 1 + aa / c
        if abs(c) < minimo { c = minimo }
        d = 1 / d
        let delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15 { break }
    }
    return h
}

/// p bilateral do t de Student com gl graus de liberdade.
func pValorT(_ t: Double, gl: Double) -> Double {
    guard t.isFinite else { return 0 }
    return betaIncompleta(gl / 2, 0.5, gl / (gl + t * t))
}

/// Teste de Mann-Kendall com correção para empates e de continuidade (como no R/ClimdexSP.R).
func mannKendall(_ x: [Double]) -> (s: Double, tau: Double, p: Double) {
    let v = x.filter { $0.isFinite }
    let n = v.count
    guard n >= 8 else { return (.nan, .nan, .nan) }
    var s = 0.0
    for k in 0..<(n - 1) {
        for j in (k + 1)..<n {
            let d = v[j] - v[k]
            s += d > 0 ? 1 : (d < 0 ? -1 : 0)
        }
    }
    var empates = [Double: Int]()
    for a in v { empates[a, default: 0] += 1 }
    let nd = Double(n)
    var varS = nd * (nd - 1) * (2 * nd + 5)
    for (_, t) in empates where t > 1 {
        let td = Double(t)
        varS -= td * (td - 1) * (2 * td + 5)
    }
    varS /= 18
    let z: Double = s > 0 ? (s - 1) / varS.squareRoot() : (s < 0 ? (s + 1) / varS.squareRoot() : 0)
    let p = 2 * normalAcumulada(-abs(z))
    return (s, s / (nd * (nd - 1) / 2), p)
}

func tendencia(anos: [Int], valores: [Double]) -> Tendencia? {
    let pares = zip(anos, valores).filter { $0.1.isFinite }
    let n = pares.count
    guard n >= 8 else { return nil }
    let t = pares.map { Double($0.0) }
    let y = pares.map { $0.1 }
    // Sen: mediana das inclinações entre todos os pares
    var inclinacoes = [Double]()
    inclinacoes.reserveCapacity(n * (n - 1) / 2)
    for i in 0..<(n - 1) {
        for j in (i + 1)..<n where t[j] != t[i] {
            inclinacoes.append((y[j] - y[i]) / (t[j] - t[i]))
        }
    }
    let sen = mediana(inclinacoes)
    // Regressão linear (mínimos quadrados)
    let mt = t.reduce(0, +) / Double(n)
    let my = y.reduce(0, +) / Double(n)
    var sxx = 0.0, sxy = 0.0
    for i in 0..<n {
        sxx += (t[i] - mt) * (t[i] - mt)
        sxy += (t[i] - mt) * (y[i] - my)
    }
    let b = sxy / sxx
    let a = my - b * mt
    var sse = 0.0
    for i in 0..<n {
        let r = y[i] - (a + b * t[i])
        sse += r * r
    }
    let gl = Double(n - 2)
    let se = (sse / gl / sxx).squareRoot()
    // série constante: o R devolve p indefinido (NaN); ajuste perfeito com inclinação: p = 0
    let pOLS = se > 0 ? pValorT(b / se, gl: gl) : (b == 0 ? .nan : 0)
    let mk = mannKendall(y)
    return Tendencia(n: n, anoInicio: Int(t.first!), anoFim: Int(t.last!), senPorDecada: 10 * sen,
                     olsPorDecada: 10 * b, erroPadraoPorDecada: 10 * se, pOLS: pOLS, mkTau: mk.tau, mkP: mk.p)
}

// MARK: - Formatação (padrão brasileiro)

enum Fmt {
    static let locale = Locale(identifier: "pt_BR")

    static func num(_ v: Double?, _ casas: Int = 0) -> String {
        guard let v, v.isFinite else { return "—" }
        return v.formatted(.number.precision(.fractionLength(casas)).locale(locale))
    }

    static func sinal(_ v: Double?, _ casas: Int = 1) -> String {
        guard let v, v.isFinite else { return "—" }
        let s = num(abs(v), casas)
        return v > 0 ? "+" + s : (v < 0 ? "−" + s : s)
    }

    static func p(_ v: Double?) -> String {
        guard let v, v.isFinite else { return "—" }
        return v < 0.001 ? "< 0,001" : num(v, 3)
    }

    /// Número para CSV no padrão brasileiro (vírgula decimal, sem separador de milhar).
    static func csv(_ v: Double?, _ casas: Int = 2) -> String {
        guard let v, v.isFinite else { return "" }
        return String(format: "%.\(casas)f", v).replacingOccurrences(of: ".", with: ",")
    }
}
