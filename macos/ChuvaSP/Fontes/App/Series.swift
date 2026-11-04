import Charts
import SwiftUI

struct SeriesView: View {
    @EnvironmentObject private var estado: EstadoApp

    private static let meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            CabecalhoRegiao(subtitulo: "Chuva mensal e diária por produto")
            mensal
            diaria
        }
    }

    // chuva mensal num intervalo de anos (x = ano*12 + mês-1)
    private var mensal: some View {
        let reg = estado.regiao
        let a0 = min(estado.anoInicial, estado.anoFinal), a1 = max(estado.anoInicial, estado.anoFinal)
        let produtos = estado.produtosVisiveis
        let pontos = produtos.flatMap { p -> [PontoLinha] in
            guard let s = estado.dados.mensal[BaseDados.chave(p, reg)] else { return [] }
            var serie = [(x: Int, y: Double)]()
            for a in a0...a1 { for m in 1...12 { serie.append((x: a * 12 + m - 1, y: s.valor(ano: a, mes: m))) } }
            return pontosEmSegmentos(p, serie)
        }
        let ticks = ticksAnos(a0, a1 + 1).map { $0 * 12 }
        return Cartao("Chuva mensal", nota: "Total de cada mês (mm). Mês com mais de 3 dias sem dado fica em branco.") {
            HStack(spacing: 16) {
                Stepper("De \(String(estado.anoInicial))", value: $estado.anoInicial, in: 1980...2026)
                Stepper("até \(String(estado.anoFinal))", value: $estado.anoFinal, in: 1980...2026)
                Spacer()
            }
            if pontos.isEmpty {
                Text("Sem dados neste intervalo.").foregroundStyle(.secondary)
            } else {
                GraficoLinhas(pontos: pontos, produtos: produtos, unidade: "mm", ticksX: ticks,
                              rotuloX: { String($0 / 12) },
                              rotuloDica: { "\(SeriesView.meses[$0 % 12])/\($0 / 12)" },
                              incluirZero: true, altura: 300)
            }
        }
    }

    // chuva diária de um ano (x = dia do ano)
    private var diaria: some View {
        let reg = estado.regiao
        let ano = estado.anoDiario
        let produtos = estado.produtosVisiveis
        let ini = DataCivil(ano: ano, mes: 1, dia: 1).numeroDoDia
        let nDias = DataCivil(ano: ano + 1, mes: 1, dia: 1).numeroDoDia - ini
        let pontos = produtos.flatMap { p -> [PontoLinha] in
            guard let s = estado.dados.diario(p, reg) else { return [] }
            let off = ini - s.inicio.numeroDoDia
            let serie = (0..<nDias).map { d -> (x: Int, y: Double) in
                let k = off + d
                return (x: d + 1, y: k >= 0 && k < s.valores.count ? s.valores[k] : .nan)
            }
            return pontosEmSegmentos(p, serie)
        }
        let ticks = (1...12).map { DataCivil(ano: ano, mes: $0, dia: 1).numeroDoDia - ini + 1 }
        let totais = produtos.compactMap { p -> (Produto, Double)? in
            let v = pontos.filter { $0.produto == p }.map(\.y)
            return v.isEmpty ? nil : (p, v.reduce(0, +))
        }
        return Cartao("Chuva diária em \(String(ano))", nota: "Dia de 0 h a 24 h UTC. Útil para conferir eventos extremos e a defasagem entre produtos.") {
            HStack(spacing: 16) {
                Stepper("Ano \(String(estado.anoDiario))", value: $estado.anoDiario, in: 1980...2026)
                Spacer()
                ForEach(totais, id: \.0) { t in
                    HStack(spacing: 4) {
                        Circle().fill(t.0.cor).frame(width: 7, height: 7)
                        Text("\(t.0.nome): \(Fmt.num(t.1, 0)) mm").font(.caption).monospacedDigit()
                    }
                }
            }
            if pontos.isEmpty {
                Text("Sem dados diários neste ano.").foregroundStyle(.secondary)
            } else {
                GraficoLinhas(pontos: pontos, produtos: produtos, unidade: "mm", ticksX: ticks,
                              rotuloX: { dia in SeriesView.meses[DataCivil(numeroDoDia: ini + dia - 1).mes - 1] },
                              rotuloDica: { dia in
                                  let d = DataCivil(numeroDoDia: ini + dia - 1)
                                  return String(format: "%02d/%02d/%04d", d.dia, d.mes, d.ano)
                              },
                              casas: 1, incluirZero: true, altura: 300)
            }
        }
    }
}
