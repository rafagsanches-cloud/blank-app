import SwiftUI

struct JanelaPrincipal: View {
    @EnvironmentObject private var estado: EstadoApp

    var body: some View {
        NavigationSplitView {
            List(selection: $estado.aba) {
                Section("Análises") {
                    ForEach(Aba.allCases) { a in
                        Label(a.titulo, systemImage: a.icone).tag(a)
                    }
                }
            }
            .navigationSplitViewColumnWidth(min: 210, ideal: 240, max: 300)
            .safeAreaInset(edge: .bottom) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Satélites e postos, 1980–2026").font(.caption).foregroundStyle(.secondary)
                    Text("Dados dentro do app; funciona sem internet.").font(.caption2).foregroundStyle(.tertiary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
            }
        } detail: {
            ScrollView {
                if let erro = estado.erro {
                    ContentUnavailableView("Não consegui ler os dados", systemImage: "exclamationmark.triangle", description: Text(erro))
                        .padding(40)
                } else {
                    ConteudoAba(aba: estado.aba ?? .visaoGeral)
                        .padding(24)
                        .frame(maxWidth: 1400, alignment: .leading)
                }
            }
            .navigationTitle(estado.aba?.titulo ?? "Chuva SP")
            .navigationSubtitle(estado.rotuloRegiao)
            .toolbar {
                ToolbarItem(placement: .navigation) {
                    Picker("Região", selection: $estado.regiao) {
                        ForEach(estado.dados.regioes) { r in
                            Text(r.rotulo).tag(r.sigla)
                        }
                    }
                    .pickerStyle(.menu)
                    .frame(minWidth: 260)
                    .help("Escolha o Estado inteiro ou uma UGRHI")
                }
                ToolbarItemGroup(placement: .primaryAction) {
                    Menu {
                        ForEach(Produto.allCases) { p in
                            Toggle(p.nome, isOn: estado.visivel(p))
                        }
                    } label: {
                        Label("Produtos", systemImage: "line.3.horizontal.decrease.circle")
                    }
                    .help("Mostrar ou esconder produtos nos gráficos")
                    Button {
                        estado.exportarAbaAtual()
                    } label: {
                        Label("Exportar CSV", systemImage: "square.and.arrow.up")
                    }
                    .help("Salvar os dados desta tela em CSV (abre no Numbers e no Excel)")
                }
            }
        }
    }
}

struct ConteudoAba: View {
    let aba: Aba

    var body: some View {
        switch aba {
        case .visaoGeral: VisaoGeralView()
        case .mapa: MapaView()
        case .series: SeriesView()
        case .extremos: ExtremosView()
        case .validacao: ValidacaoView()
        case .postos: PostosView()
        case .produtos: ProdutosView()
        }
    }
}

/// Cabeçalho comum: nome da região e área.
struct CabecalhoRegiao: View {
    @EnvironmentObject var estado: EstadoApp
    let subtitulo: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(estado.rotuloRegiao)
                .font(.system(size: 28, weight: .regular, design: .serif))
            HStack(spacing: 8) {
                if let r = estado.regiaoAtual, r.areaKm2 > 0 {
                    Text("\(Fmt.num(r.areaKm2, 0)) km²")
                    Text("·")
                }
                Text(subtitulo)
            }
            .font(.callout)
            .foregroundStyle(.secondary)
        }
    }
}
