import AppKit
import SwiftUI
import UniformTypeIdentifiers

// MARK: - Produtos e cores (mesma paleta do painel e do app Streamlit)

enum Produto: String, CaseIterable, Identifiable, Hashable {
    case CHIRPS, IMERG, PERSIANN, CMORPH, GPCP, POSTOS, ANA

    var id: String { rawValue }
    var nome: String {
        switch self {
        case .POSTOS: return "Postos (média)"
        case .ANA: return "ANA (HidroWeb)"
        default: return rawValue
        }
    }
    static let satelites: [Produto] = [.CHIRPS, .IMERG, .PERSIANN, .CMORPH, .GPCP]

    private var hex: (claro: UInt32, escuro: UInt32) {
        switch self {
        case .CHIRPS: return (0x2A78D6, 0x3987E5)
        case .IMERG: return (0xEB6834, 0xD95926)
        case .PERSIANN: return (0x1BAF7A, 0x199E70)
        case .CMORPH: return (0xEDA100, 0xC98500)
        case .GPCP: return (0xE87BA4, 0xD55181)
        case .POSTOS: return (0x008300, 0x0CA30C)
        case .ANA: return (0x7E57C2, 0xA98BEB)
        }
    }

    var cor: Color {
        let h = hex
        return Color(nsColor: NSColor(name: nil) { aparencia in
            let escuro = aparencia.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            return NSColor(hex: escuro ? h.escuro : h.claro)
        })
    }
}

extension NSColor {
    convenience init(hex: UInt32) {
        self.init(srgbRed: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255,
                  blue: CGFloat(hex & 0xFF) / 255, alpha: 1)
    }
}

// MARK: - Telas

enum Aba: String, CaseIterable, Identifiable {
    case visaoGeral, mapa, series, extremos, validacao, postos, ana, produtos

    var id: String { rawValue }

    var titulo: String {
        switch self {
        case .visaoGeral: return "Visão geral"
        case .mapa: return "Mapa das UGRHIs"
        case .series: return "Séries mensais e diárias"
        case .extremos: return "Extremos (RClimDex)"
        case .validacao: return "Satélite × postos"
        case .postos: return "Postos pluviométricos"
        case .ana: return "Postos da ANA"
        case .produtos: return "Produtos e fontes"
        }
    }

    var icone: String {
        switch self {
        case .visaoGeral: return "chart.xyaxis.line"
        case .mapa: return "map"
        case .series: return "calendar"
        case .extremos: return "cloud.bolt.rain"
        case .validacao: return "checkmark.seal"
        case .postos: return "mappin.and.ellipse"
        case .ana: return "drop"
        case .produtos: return "info.circle"
        }
    }
}

enum ModoMapa: String, CaseIterable, Identifiable {
    case media, tendencia
    var id: String { rawValue }
    var titulo: String { self == .media ? "Média 2001–2020" : "Tendência (Sen)" }
}

/// Rede de postos usada na comparação com os satélites.
enum FonteValidacao: String, CaseIterable, Identifiable {
    case ghcn, ana
    var id: String { rawValue }
    var titulo: String { self == .ghcn ? "Postos do GHCN-Daily" : "Postos da ANA (HidroWeb)" }
}

enum Metrica: String, CaseIterable, Identifiable {
    case rDiario, rMensal, viesPct, kge, csi
    var id: String { rawValue }

    var titulo: String {
        switch self {
        case .rDiario: return "r diário"
        case .rMensal: return "r mensal"
        case .viesPct: return "Viés (%)"
        case .kge: return "KGE"
        case .csi: return "CSI"
        }
    }

    func valor(_ v: ValidacaoDTO) -> Double? {
        switch self {
        case .rDiario: return v.rDiario
        case .rMensal: return v.rMensal
        case .viesPct: return v.viesPct
        case .kge: return v.kge
        case .csi: return v.csi
        }
    }
}

// MARK: - Dados carregados

struct Regiao: Identifiable, Hashable {
    let sigla: String
    let codigo: Int
    let nome: String
    let rotulo: String
    let areaKm2: Double
    /// anéis em (lon, lat)
    let aneis: [[CGPoint]]
    var id: String { sigla }

    // CGPoint não é Hashable no SDK do macOS 14: a sigla identifica a região
    static func == (a: Regiao, b: Regiao) -> Bool { a.sigla == b.sigla }
    func hash(into h: inout Hasher) { h.combine(sigla) }
}

struct SerieMensal {
    let inicio: DataCivil
    let valores: [Double]

    func valor(ano: Int, mes: Int) -> Double {
        let k = (ano - inicio.ano) * 12 + (mes - inicio.mes)
        return k >= 0 && k < valores.count ? valores[k] : .nan
    }
}

final class BaseDados {
    let fonte: FonteDados?
    let regioes: [Regiao]
    let anual: [String: [Int: Double]]
    let mensal: [String: SerieMensal]
    let indiceDiario: [String: DiarioIndiceDTO]
    let postos: [PostoDTO]
    let postosPorAno: [String: [PostosAnoDTO]]
    let validacao: [ValidacaoDTO]
    let produtos: [ProdutoDTO]
    let fontes: [FonteDTO]
    // ANA (HidroWeb): arquivos ana_*; se faltarem, o app funciona como antes
    let anaPostos: [AnaPostoDTO]
    let anaPostosPorAno: [String: [PostosAnoDTO]]
    let anaValidacao: [ValidacaoDTO]
    let anaResumo: AnaResumoDTO?
    private var anaMatrizMensal: [Float32]?
    private var anaMatrizAnual: [Float32]?
    private var cacheDiario = [String: SerieDiaria]()
    private var cacheIndices = [String: ResultadoIndices]()

    static func chave(_ p: Produto, _ sigla: String) -> String { p.rawValue + "|" + sigla }

    init(fonte: FonteDados) throws {
        self.fonte = fonte
        regioes = try fonte.ler("regioes.json", como: [RegiaoDTO].self)
            .map { r in
                Regiao(sigla: r.sigla, codigo: r.codigo, nome: r.nome, rotulo: r.rotulo, areaKm2: r.areaKm2,
                       aneis: r.aneis.map { anel in anel.map { CGPoint(x: $0[0], y: $0[1]) } })
            }
            .sorted { $0.codigo < $1.codigo }
        var an = [String: [Int: Double]]()
        for a in try fonte.ler("anual.json", como: [AnualDTO].self) + ((try? fonte.ler("ana_anual.json", como: [AnualDTO].self)) ?? []) {
            guard let mm = a.mm, let p = Produto(rawValue: a.produto) else { continue }
            an[BaseDados.chave(p, a.sigla), default: [:]][a.ano] = mm
        }
        anual = an
        var me = [String: SerieMensal]()
        for m in try fonte.ler("mensal.json", como: [MensalDTO].self) + ((try? fonte.ler("ana_mensal.json", como: [MensalDTO].self)) ?? []) {
            guard let p = Produto(rawValue: m.produto), let ini = DataCivil(texto: m.inicio) else { continue }
            me[BaseDados.chave(p, m.sigla)] = SerieMensal(inicio: ini, valores: m.valores.map { $0 ?? .nan })
        }
        mensal = me
        var di = [String: DiarioIndiceDTO]()
        for d in try fonte.ler("diario_indice.json", como: [DiarioIndiceDTO].self)
            + ((try? fonte.ler("ana_diario_indice.json", como: [DiarioIndiceDTO].self)) ?? []) {
            if let p = Produto(rawValue: d.produto) { di[BaseDados.chave(p, d.sigla)] = d }
        }
        indiceDiario = di
        postos = try fonte.ler("postos.json", como: [PostoDTO].self)
        let porAno = try fonte.ler("postos_por_ano.json", como: [PostosAnoDTO].self)
        postosPorAno = Dictionary(grouping: porAno, by: \.sigla)
        validacao = try fonte.ler("validacao.json", como: [ValidacaoDTO].self)
        produtos = try fonte.ler("produtos.json", como: [ProdutoDTO].self)
        fontes = try fonte.ler("fontes.json", como: [FonteDTO].self)
        anaPostos = (try? fonte.ler("ana_postos.json", como: [AnaPostoDTO].self)) ?? []
        anaPostosPorAno = Dictionary(grouping: (try? fonte.ler("ana_postos_por_ano.json", como: [PostosAnoDTO].self)) ?? [], by: \.sigla)
        anaValidacao = (try? fonte.ler("ana_validacao.json", como: [ValidacaoDTO].self)) ?? []
        anaResumo = try? fonte.ler("ana_resumo.json", como: AnaResumoDTO.self)
    }

    init() {
        fonte = nil
        regioes = [Regiao(sigla: "SP", codigo: 0, nome: "Estado de São Paulo", rotulo: "Estado de São Paulo", areaKm2: 0, aneis: [])]
        anual = [:]
        mensal = [:]
        indiceDiario = [:]
        postos = []
        postosPorAno = [:]
        validacao = []
        produtos = []
        fontes = []
        anaPostos = []
        anaPostosPorAno = [:]
        anaValidacao = []
        anaResumo = nil
    }

    func diario(_ p: Produto, _ sigla: String) -> SerieDiaria? {
        let k = BaseDados.chave(p, sigla)
        if let s = cacheDiario[k] { return s }
        guard let idx = indiceDiario[k], let fonte, let s = try? fonte.serieDiaria(idx) else { return nil }
        cacheDiario[k] = s
        return s
    }

    /// Totais mensais (desde ana_resumo.inicioMensal) de um posto da ANA; NaN = falta.
    func anaMensal(_ p: AnaPostoDTO) -> [Double] {
        guard let r = anaResumo else { return [] }
        if anaMatrizMensal == nil { anaMatrizMensal = (try? fonte?.floats("ana_postos_mensal.f32")) ?? [] }
        return BaseDados.linha(anaMatrizMensal ?? [], p.linha, r.meses)
    }

    /// Totais anuais (desde ana_resumo.anoInicial) de um posto da ANA; NaN = ano incompleto.
    func anaAnual(_ p: AnaPostoDTO) -> [Double] {
        guard let r = anaResumo else { return [] }
        if anaMatrizAnual == nil { anaMatrizAnual = (try? fonte?.floats("ana_postos_anual.f32")) ?? [] }
        return BaseDados.linha(anaMatrizAnual ?? [], p.linha, r.anos)
    }

    private static func linha(_ m: [Float32], _ k: Int, _ n: Int) -> [Double] {
        let ini = k * n
        guard n > 0, ini >= 0, ini + n <= m.count else { return [] }
        return m[ini..<(ini + n)].map { Double($0) }
    }

    func indices(_ p: Produto, _ sigla: String, _ par: ParametrosIndices) -> ResultadoIndices? {
        let k = "\(p.rawValue)|\(sigla)|\(par.baseInicio)|\(par.baseFim)|\(par.limiarUmido)|\(par.nn)|\(par.sequenciasCruzamAnos)"
        if let r = cacheIndices[k] { return r }
        guard let s = diario(p, sigla) else { return nil }
        let r = calcularIndices(s, par)
        cacheIndices[k] = r
        return r
    }
}

// MARK: - Estado do app

/// Períodos de referência (os mesmos do painel e do Excel).
enum Periodos {
    static let media = 2001...2020
    static let postos = 1980...1999
}

@MainActor
final class EstadoApp: ObservableObject {
    @Published var aba: Aba? = .visaoGeral
    @Published var regiao = "SP"
    @Published var visiveis: Set<Produto> = Set(Produto.allCases)
    @Published var mapaProduto: Produto = .CHIRPS
    @Published var mapaModo: ModoMapa = .media
    @Published var mapaPostos = false
    @Published var indice: Indice = .PRCPTOT
    @Published var parametros = ParametrosIndices()
    @Published var anoInicial = 1981
    @Published var anoFinal = 2026
    @Published var anoDiario = 2024
    @Published var metrica: Metrica = .rDiario
    @Published var busca = ""
    @Published var anaBusca = ""
    @Published var anaSelecionado: String?
    @Published var fonteValidacao: FonteValidacao = .ghcn

    let dados: BaseDados
    let erro: String?

    init() {
        do {
            dados = try BaseDados(fonte: try FonteDados.localizar())
            erro = nil
        } catch {
            dados = BaseDados()
            erro = error.localizedDescription
        }
        // argumentos opcionais: --aba <nome> --regiao <sigla>
        let args = CommandLine.arguments
        if let i = args.firstIndex(of: "--aba"), i + 1 < args.count, let a = Aba(rawValue: args[i + 1]) { aba = a }
        if let i = args.firstIndex(of: "--regiao"), i + 1 < args.count { regiao = args[i + 1] }
    }

    var regiaoAtual: Regiao? { dados.regioes.first { $0.sigla == regiao } }
    var rotuloRegiao: String { regiaoAtual?.rotulo ?? regiao }
    var produtosVisiveis: [Produto] { Produto.allCases.filter { visiveis.contains($0) } }

    func visivel(_ p: Produto) -> Binding<Bool> {
        Binding(get: { self.visiveis.contains(p) },
                set: { novo in if novo { self.visiveis.insert(p) } else { self.visiveis.remove(p) } })
    }

    // séries anuais
    func serieAnual(_ p: Produto, _ sigla: String) -> [(ano: Int, mm: Double)] {
        (dados.anual[BaseDados.chave(p, sigla)] ?? [:]).sorted { $0.key < $1.key }.map { ($0.key, $0.value) }
    }

    func media(_ p: Produto, _ sigla: String, _ periodo: ClosedRange<Int> = Periodos.media) -> Double? {
        let v = serieAnual(p, sigla).filter { periodo.contains($0.ano) }.map(\.mm)
        return v.isEmpty ? nil : v.reduce(0, +) / Double(v.count)
    }

    func tendenciaAnual(_ p: Produto, _ sigla: String) -> Tendencia? {
        let s = serieAnual(p, sigla)
        return tendencia(anos: s.map(\.ano), valores: s.map(\.mm))
    }

    func climatologia(_ p: Produto, _ sigla: String) -> [Double] {
        guard let s = dados.mensal[BaseDados.chave(p, sigla)] else { return [] }
        let periodo = p == .POSTOS ? Periodos.postos : Periodos.media
        return (1...12).map { mes in
            let v = periodo.map { s.valor(ano: $0, mes: mes) }.filter(\.isFinite)
            return v.isEmpty ? .nan : v.reduce(0, +) / Double(v.count)
        }
    }

    func postosNaRegiao(_ sigla: String) -> [PostoDTO] {
        sigla == "SP" ? dados.postos : dados.postos.filter { $0.sigla == sigla }
    }

    var postosFiltrados: [PostoDTO] {
        let q = busca.trimmingCharacters(in: .whitespaces).lowercased()
        let base = postosNaRegiao(regiao)
        guard !q.isEmpty else { return base }
        return base.filter { "\($0.id) \($0.nome) \($0.rede) \($0.codigoOriginal)".lowercased().contains(q) }
    }

    func validacoes(_ sigla: String, fonte: FonteValidacao = .ghcn) -> [ValidacaoDTO] {
        let base = fonte == .ghcn ? dados.validacao : dados.anaValidacao
        return sigla == "SP" ? base : base.filter { $0.sigla == sigla }
    }

    func medianaValidacao(_ p: Produto, _ sigla: String, _ m: Metrica, fonte: FonteValidacao = .ghcn) -> (valor: Double, postos: Int)? {
        let v = validacoes(sigla, fonte: fonte).filter { $0.produto == p.rawValue }.compactMap { m.valor($0) }
        guard !v.isEmpty else { return nil }
        return (mediana(v), v.count)
    }

    // postos da ANA
    func anaPostosNaRegiao(_ sigla: String) -> [AnaPostoDTO] {
        sigla == "SP" ? dados.anaPostos : dados.anaPostos.filter { $0.sigla == sigla }
    }

    var anaPostosFiltrados: [AnaPostoDTO] {
        let q = anaBusca.trimmingCharacters(in: .whitespaces).lowercased()
        let base = anaPostosNaRegiao(regiao)
        guard !q.isEmpty else { return base }
        return base.filter { "\($0.id) \($0.nome) \($0.municipio) \($0.operadora)".lowercased().contains(q) }
    }

    var anaPostoSelecionado: AnaPostoDTO? {
        guard let id = anaSelecionado else { return nil }
        return dados.anaPostos.first { $0.id == id }
    }

    /// Valores do mapa por UGRHI (média 2001–2020 ou tendência de Sen do total anual).
    func valoresMapa() -> [String: Double] {
        var out = [String: Double]()
        for r in dados.regioes where r.sigla != "SP" {
            switch mapaModo {
            case .media: out[r.sigla] = media(mapaProduto, r.sigla)
            case .tendencia: out[r.sigla] = tendenciaAnual(mapaProduto, r.sigla)?.senPorDecada
            }
        }
        return out
    }

    // MARK: exportação

    func exportarAbaAtual() {
        let (nome, texto) = csvAbaAtual()
        Arquivos.salvar(texto: texto, nomeSugerido: nome, tipo: .commaSeparatedText)
    }

    private func linhaCSV(_ campos: [String]) -> String { campos.joined(separator: ";") }

    func csvAbaAtual() -> (String, String) {
        let reg = regiaoAtual?.sigla ?? regiao
        var linhas = [String]()
        let nome: String
        switch aba ?? .visaoGeral {
        case .visaoGeral:
            nome = "chuva_anual_\(reg).csv"
            linhas.append(linhaCSV(["ano"] + Produto.allCases.map(\.nome)))
            let series = Produto.allCases.map { p in Dictionary(uniqueKeysWithValues: serieAnual(p, reg).map { ($0.ano, $0.mm) }) }
            let anos = Set(series.flatMap(\.keys)).sorted()
            for a in anos { linhas.append(linhaCSV([String(a)] + series.map { Fmt.csv($0[a], 1) })) }
        case .mapa:
            nome = "mapa_\(mapaProduto.rawValue)_\(mapaModo.rawValue).csv"
            linhas.append(linhaCSV(["sigla", "ugrhi", mapaModo == .media ? "media_2001_2020_mm" : "sen_mm_por_decada"]))
            let v = valoresMapa()
            for r in dados.regioes where r.sigla != "SP" { linhas.append(linhaCSV([r.sigla, r.rotulo, Fmt.csv(v[r.sigla], 1)])) }
        case .series:
            nome = "chuva_mensal_\(reg).csv"
            linhas.append(linhaCSV(["ano", "mes"] + Produto.allCases.map(\.nome)))
            let ss = Produto.allCases.map { dados.mensal[BaseDados.chave($0, reg)] }
            for a in min(anoInicial, anoFinal)...max(anoInicial, anoFinal) {
                for m in 1...12 { linhas.append(linhaCSV([String(a), String(m)] + ss.map { Fmt.csv($0?.valor(ano: a, mes: m), 1) })) }
            }
        case .extremos:
            nome = "indices_etccdi_\(reg).csv"
            linhas.append(linhaCSV(["produto", "ano"] + Indice.allCases.map { $0.nome(nn: parametros.nn) }))
            for p in Produto.allCases {
                guard let r = dados.indices(p, reg, parametros) else { continue }
                for (k, a) in r.anos.enumerated() {
                    linhas.append(linhaCSV([p.rawValue, String(a)] + Indice.allCases.map { Fmt.csv(r.valores[$0]?[k], 2) }))
                }
            }
        case .validacao:
            nome = "validacao_\(reg).csv"
            linhas.append(linhaCSV(["produto", "posto", "ugrhi", "rede", "dias_comuns", "r_diario", "r_mensal", "vies_pct", "kge", "csi"]))
            for v in validacoes(reg, fonte: fonteValidacao) {
                linhas.append(linhaCSV([v.produto, v.estacao, v.sigla, v.rede, String(v.diasComuns), Fmt.csv(v.rDiario, 3),
                                        Fmt.csv(v.rMensal, 3), Fmt.csv(v.viesPct, 1), Fmt.csv(v.kge, 3), Fmt.csv(v.csi, 3)]))
            }
        case .postos:
            nome = "postos_\(reg).csv"
            linhas.append(linhaCSV(["codigo_ghcn", "nome", "rede", "codigo_original", "ugrhi", "lat", "lon", "altitude_m", "inicio", "fim", "dias_com_dado"]))
            for p in postosFiltrados {
                linhas.append(linhaCSV([p.id, p.nome, p.rede, p.codigoOriginal, p.sigla, Fmt.csv(p.lat, 4), Fmt.csv(p.lon, 4),
                                        Fmt.csv(p.altitude, 0), p.inicio, p.fim, String(p.dias)]))
            }
        case .ana:
            nome = "postos_ana_\(reg).csv"
            linhas.append(linhaCSV(["codigo_ana", "nome", "municipio", "operadora", "ugrhi", "lat", "lon", "altitude_m", "inicio", "fim",
                                    "dias_com_dado", "anos_completos", "media_anual_mm", "operando", "telemetrica"]))
            for p in anaPostosFiltrados {
                linhas.append(linhaCSV([p.id, p.nome, p.municipio, p.operadora, p.sigla, Fmt.csv(p.lat, 4), Fmt.csv(p.lon, 4),
                                        Fmt.csv(p.altitude, 0), p.inicio, p.fim, String(p.dias), String(p.anosCompletos),
                                        Fmt.csv(p.mediaAnual, 0), p.operando ? "sim" : "não", p.telemetrica ? "sim" : "não"]))
            }
        case .produtos:
            nome = "produtos_satelite.csv"
            linhas.append(linhaCSV(["Produto", "Tipo de Sensor Principal", "Série Histórica", "Resolução Espacial", "Foco Principal", "Versão usada", "Período baixado"]))
            for p in dados.produtos { linhas.append(linhaCSV([p.produto, p.sensor, p.serie, p.resolucao, p.foco, p.versao, p.periodo])) }
        }
        // BOM para o Excel reconhecer os acentos
        return (nome, "\u{FEFF}" + linhas.joined(separator: "\n") + "\n")
    }

    func exportarRClimDex(_ p: Produto) {
        guard let s = dados.diario(p, regiao) else { return }
        var linhas = [String]()
        linhas.reserveCapacity(s.valores.count)
        for (i, v) in s.valores.enumerated() {
            let d = DataCivil(numeroDoDia: s.inicio.numeroDoDia + i)
            let pr = v.isFinite ? String(format: "%.1f", v) : "-99.9"
            linhas.append("\(d.ano) \(d.mes) \(d.dia) \(pr) -99.9 -99.9")
        }
        Arquivos.salvar(texto: linhas.joined(separator: "\n") + "\n", nomeSugerido: "\(p.rawValue)_\(regiao)_rclimdex.txt", tipo: .plainText)
    }
}

enum Arquivos {
    @MainActor
    static func salvar(texto: String, nomeSugerido: String, tipo: UTType) {
        let painel = NSSavePanel()
        painel.nameFieldStringValue = nomeSugerido
        painel.allowedContentTypes = [tipo]
        painel.canCreateDirectories = true
        guard painel.runModal() == .OK, let url = painel.url else { return }
        do {
            try texto.write(to: url, atomically: true, encoding: .utf8)
        } catch {
            NSAlert(error: error).runModal()
        }
    }
}
