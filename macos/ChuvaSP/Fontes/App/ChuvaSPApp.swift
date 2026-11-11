import AppKit
import SwiftUI

@main
struct ChuvaSPApp: App {
    @NSApplicationDelegateAdaptor(Delegado.self) private var delegado
    @StateObject private var estado = EstadoApp()

    var body: some Scene {
        WindowGroup("Chuva SP") {
            JanelaPrincipal()
                .environmentObject(estado)
                .frame(minWidth: 1040, minHeight: 700)
        }
        .defaultSize(width: 1360, height: 900)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandGroup(after: .saveItem) {
                Button("Exportar dados desta tela (CSV)…") { estado.exportarAbaAtual() }
                    .keyboardShortcut("e", modifiers: [.command])
            }
        }
    }
}

@MainActor
final class Delegado: NSObject, NSApplicationDelegate {
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let args = CommandLine.arguments
        if let i = args.firstIndex(of: "--capturas"), i + 1 < args.count {
            Capturas.gerar(pasta: URL(fileURLWithPath: args[i + 1]))
            exit(0)
        }
    }
}

/// Modo usado no teste automático: desenha cada tela em PNG, sem abrir janela, e encerra.
@MainActor
enum Capturas {
    static func gerar(pasta: URL) {
        try? FileManager.default.createDirectory(at: pasta, withIntermediateDirectories: true)
        let estado = EstadoApp()
        if let erro = estado.erro {
            print("erro ao carregar dados: \(erro)")
            exit(1)
        }
        let cenarios: [(String, Aba, String)] = [
            ("1_visao_geral", .visaoGeral, "SP"),
            ("2_mapa", .mapa, "UGRHI13"),
            ("3_series", .series, "UGRHI05"),
            ("4_extremos", .extremos, "UGRHI13"),
            ("5_validacao", .validacao, "SP"),
            ("6_postos", .postos, "UGRHI13"),
            ("7_produtos", .produtos, "SP"),
            ("8_postos_ana", .ana, "UGRHI13"),
            ("9_validacao_ana", .validacao, "SP"),
        ]
        for (nome, aba, regiao) in cenarios {
            for (sufixo, aparencia) in [("claro", NSAppearance.Name.aqua), ("escuro", NSAppearance.Name.darkAqua)] {
                estado.aba = aba
                estado.regiao = regiao
                estado.fonteValidacao = nome == "9_validacao_ana" ? .ana : .ghcn
                if aba == .ana {
                    // mostra o detalhe do posto com mais anos completos na região
                    estado.anaSelecionado = estado.anaPostosNaRegiao(regiao).max { $0.anosCompletos < $1.anosCompletos }?.id
                }
                let conteudo = ConteudoAba(aba: aba)
                    .environmentObject(estado)
                    .padding(24)
                    .frame(width: 1180)
                    .background(Color(nsColor: .windowBackgroundColor))
                    .environment(\.colorScheme, sufixo == "claro" ? .light : .dark)
                NSAppearance(named: aparencia)?.performAsCurrentDrawingAppearance {
                    let r = ImageRenderer(content: conteudo)
                    r.scale = 1
                    r.proposedSize = ProposedViewSize(width: 1180, height: nil)
                    if let img = r.nsImage, let tiff = img.tiffRepresentation,
                       let rep = NSBitmapImageRep(data: tiff), let png = rep.representation(using: .png, properties: [:]) {
                        try? png.write(to: pasta.appendingPathComponent("\(nome)_\(sufixo).png"))
                        print("captura: \(nome)_\(sufixo).png")
                    } else {
                        print("falha na captura: \(nome)_\(sufixo)")
                    }
                }
            }
        }
    }
}
