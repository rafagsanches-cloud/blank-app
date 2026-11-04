// Leitura dos dados que acompanham o app (pasta Dados, gerada por macos/gerar_dados.py).

import Foundation

struct RegiaoDTO: Decodable {
    let sigla: String
    let codigo: Int
    let nome: String
    let rotulo: String
    let areaKm2: Double
    let aneis: [[[Double]]]
}

struct AnualDTO: Decodable {
    let produto: String
    let sigla: String
    let ano: Int
    let mm: Double?
}

struct MensalDTO: Decodable {
    let produto: String
    let sigla: String
    let inicio: String
    let valores: [Double?]
}

struct DiarioIndiceDTO: Decodable {
    let produto: String
    let sigla: String
    let inicio: String
    let dias: Int
    let arquivo: String
}

struct PostoDTO: Decodable, Identifiable, Hashable {
    let id: String
    let nome: String
    let rede: String
    let codigoOriginal: String
    let sigla: String
    let lat: Double
    let lon: Double
    let altitude: Double?
    let inicio: String
    let fim: String
    let dias: Int
}

struct PostosAnoDTO: Decodable {
    let ano: Int
    let sigla: String
    let postos: Int
}

struct ValidacaoDTO: Decodable, Identifiable {
    let produto: String
    let estacao: String
    let sigla: String
    let rede: String
    let rDiario: Double?
    let rMensal: Double?
    let viesPct: Double?
    let kge: Double?
    let csi: Double?
    let diasComuns: Int

    var id: String { produto + "|" + estacao }
}

struct ProdutoDTO: Decodable, Identifiable {
    let produto: String
    let sensor: String
    let serie: String
    let resolucao: String
    let foco: String
    let versao: String
    let periodo: String
    let url: String

    var id: String { produto }
}

struct FonteDTO: Decodable, Identifiable {
    let grupo: String
    let base: String
    let endereco: String
    let descricao: String

    var id: String { base }
}

enum ErroDados: LocalizedError {
    case pastaNaoEncontrada
    case arquivo(String, Error)

    var errorDescription: String? {
        switch self {
        case .pastaNaoEncontrada:
            return "Não encontrei a pasta Dados do aplicativo."
        case let .arquivo(nome, erro):
            return "Falha ao ler \(nome): \(erro.localizedDescription)"
        }
    }
}

final class FonteDados {
    let pasta: URL

    init(pasta: URL) { self.pasta = pasta }

    /// Procura a pasta Dados: dentro do app (Contents/Resources/Dados), na variável
    /// CHUVASP_DADOS, ao lado do executável ou na pasta atual.
    static func localizar() throws -> FonteDados {
        var candidatas = [URL]()
        if let r = Bundle.main.resourceURL { candidatas.append(r.appendingPathComponent("Dados")) }
        if let env = ProcessInfo.processInfo.environment["CHUVASP_DADOS"] { candidatas.append(URL(fileURLWithPath: env)) }
        let exe = URL(fileURLWithPath: CommandLine.arguments[0]).deletingLastPathComponent()
        candidatas.append(exe.appendingPathComponent("Dados"))
        candidatas.append(exe.deletingLastPathComponent().appendingPathComponent("Dados"))
        candidatas.append(URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("Dados"))
        for c in candidatas where FileManager.default.fileExists(atPath: c.appendingPathComponent("regioes.json").path) {
            return FonteDados(pasta: c)
        }
        throw ErroDados.pastaNaoEncontrada
    }

    func ler<T: Decodable>(_ nome: String, como tipo: T.Type) throws -> T {
        let url = pasta.appendingPathComponent(nome)
        do {
            let dados = try Data(contentsOf: url)
            return try JSONDecoder().decode(T.self, from: dados)
        } catch {
            throw ErroDados.arquivo(nome, error)
        }
    }

    /// Lê uma série diária gravada em Float32 little-endian (NaN = falta).
    func serieDiaria(_ idx: DiarioIndiceDTO) throws -> SerieDiaria {
        let url = pasta.appendingPathComponent("diario").appendingPathComponent(idx.arquivo)
        let dados: Data
        do { dados = try Data(contentsOf: url) } catch { throw ErroDados.arquivo(idx.arquivo, error) }
        let n = min(idx.dias, dados.count / 4)
        var brutos = [Float32](repeating: .nan, count: n)
        _ = brutos.withUnsafeMutableBytes { dados.copyBytes(to: $0, count: n * 4) }
        let valores = brutos.map { Double(Float32(bitPattern: UInt32(littleEndian: $0.bitPattern))) }
        guard let ini = DataCivil(texto: idx.inicio) else {
            throw ErroDados.arquivo(idx.arquivo, NSError(domain: "ChuvaSP", code: 1))
        }
        return SerieDiaria(produto: idx.produto, sigla: idx.sigla, inicio: ini, valores: valores)
    }
}
