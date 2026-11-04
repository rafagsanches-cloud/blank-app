// Teste dos cálculos do app contra o ClimdexSP em R.
// Uso: testes <pasta Dados> <referencia_climdexsp.json>

import Foundation

struct TendRef: Decodable {
    let indice: String
    let n: Int?
    let sen: Double?
    let ols: Double?
    let p_ols: Double?
    let mk_p: Double?
}

struct CasoRef: Decodable {
    let produto: String
    let sigla: String
    let p95: Double
    let p99: Double
    let anos: [Int]
    let indices: [String: [Double?]]
    let tendencias: [TendRef]
}

let args = CommandLine.arguments
guard args.count >= 3 else {
    print("uso: testes <pasta Dados> <referencia.json>")
    exit(2)
}
let fonte = FonteDados(pasta: URL(fileURLWithPath: args[1]))
let casos = try JSONDecoder().decode([CasoRef].self, from: Data(contentsOf: URL(fileURLWithPath: args[2])))
let indiceDiario = try fonte.ler("diario_indice.json", como: [DiarioIndiceDTO].self)

var falhas = 0
var comparacoes = 0

func confere(_ rotulo: String, _ obtido: Double, _ esperado: Double?, tol: Double = 1e-6) {
    comparacoes += 1
    guard let e = esperado else {
        if obtido.isFinite {
            falhas += 1
            print("FALHA \(rotulo): esperado falta, obtido \(obtido)")
        }
        return
    }
    let dif = abs(obtido - e)
    if !(dif <= tol * max(1, abs(e))) {
        falhas += 1
        print("FALHA \(rotulo): esperado \(e), obtido \(obtido)")
    }
}

let p = ParametrosIndices(baseInicio: 1981, baseFim: 2010, limiarUmido: 1, nn: 50, sequenciasCruzamAnos: true, maxFaltasAno: 15)
for caso in casos {
    guard let idx = indiceDiario.first(where: { $0.produto == caso.produto && $0.sigla == caso.sigla }) else {
        print("FALHA: série \(caso.produto) \(caso.sigla) não encontrada")
        falhas += 1
        continue
    }
    let serie = try fonte.serieDiaria(idx)
    let r = calcularIndices(serie, p)
    let nome = "\(caso.produto) \(caso.sigla)"
    confere("\(nome) p95", r.p95, caso.p95)
    confere("\(nome) p99", r.p99, caso.p99)
    if r.anos != caso.anos { falhas += 1; print("FALHA \(nome): anos diferentes \(r.anos.first ?? 0)-\(r.anos.last ?? 0)") }
    for ind in Indice.allCases {
        let chave = ind.nome(nn: p.nn)
        guard let ref = caso.indices[chave] else { falhas += 1; print("FALHA: referência sem \(chave)"); continue }
        let obt = r.valores[ind] ?? []
        for (k, ano) in caso.anos.enumerated() where k < obt.count {
            confere("\(nome) \(chave) \(ano)", obt[k], ref[k])
        }
        if let tr = caso.tendencias.first(where: { $0.indice == chave }) {
            let t = tendencia(anos: r.anos, valores: obt)
            if let t {
                confere("\(nome) \(chave) Sen", t.senPorDecada, tr.sen)
                confere("\(nome) \(chave) OLS", t.olsPorDecada, tr.ols)
                confere("\(nome) \(chave) p OLS", t.pOLS, tr.p_ols, tol: 1e-5)
                confere("\(nome) \(chave) p MK", t.mkP, tr.mk_p, tol: 1e-5)
            } else if tr.sen != nil {
                falhas += 1
                print("FALHA \(nome) \(chave): tendência não calculada")
            }
        }
    }
    print("ok: \(nome) – \(r.anos.count) anos, p95 = \(String(format: "%.3f", r.p95)) mm")
}

// datas
let d = DataCivil(ano: 2024, mes: 2, dia: 29)
if DataCivil(numeroDoDia: d.numeroDoDia) != d || DataCivil(ano: 1970, mes: 1, dia: 1).numeroDoDia != 0 {
    falhas += 1
    print("FALHA: conversão de datas")
}

print("\(comparacoes) comparações, \(falhas) falhas")
exit(falhas == 0 ? 0 : 1)
