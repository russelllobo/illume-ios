#if os(iOS)
import IllumeCore
import SwiftUI

struct ReaderView: View {
    @EnvironmentObject private var app: IllumeAppModel
    @Environment(\.dismiss) private var dismiss
    @State private var settingsOpen = false
    @State private var currentIndex = 0

    var body: some View {
        let theme = app.readerSettings.theme

        ZStack {
            theme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                ReaderToolbar(settingsOpen: $settingsOpen) {
                    app.closeReader()
                    dismiss()
                }

                if let book = app.activeBook {
                    ScrollViewReader { proxy in
                        ScrollView {
                            LazyVStack(alignment: .leading, spacing: 18) {
                                ForEach(Array(book.paragraphs.enumerated()), id: \.element.id) { index, paragraph in
                                    ParagraphView(paragraph: paragraph, index: index)
                                        .id(paragraph.id)
                                        .onAppear {
                                            currentIndex = index
                                            app.saveProgress(index: index, page: paragraph.pageNumber ?? 1)
                                        }
                                }
                            }
                            .frame(maxWidth: app.readerSettings.lineWidth * 12)
                            .padding(.horizontal, 24)
                            .padding(.top, 16)
                            .padding(.bottom, 120)
                            .frame(maxWidth: .infinity)
                        }
                        .scrollIndicators(.hidden)
                        .onAppear {
                            if let row = app.activeBookRow,
                               book.paragraphs.indices.contains(row.currentIndex) {
                                proxy.scrollTo(book.paragraphs[row.currentIndex].id, anchor: .top)
                            }
                        }
                    }
                }
            }

            if let imageUrl = app.readerImageResponse?.imageUrl,
               let url = URL(string: imageUrl) {
                ReaderImageOverlay(url: url) {
                    withAnimation(IllumeTheme.spring) {
                        app.readerImageResponse = nil
                    }
                }
            }
        }
        .foregroundStyle(theme.foreground)
        .sheet(isPresented: $settingsOpen) {
            ReaderSettingsSheet()
                .presentationDetents([.medium])
                .presentationCornerRadius(30)
        }
    }
}

struct ReaderToolbar: View {
    @Binding var settingsOpen: Bool
    let close: () -> Void

    var body: some View {
        HStack {
            SoftIconButton(systemName: "chevron.down", action: close)
            Spacer()
            SoftIconButton(systemName: "textformat.size") { settingsOpen = true }
        }
        .padding(.horizontal, 18)
        .padding(.top, 8)
        .padding(.bottom, 8)
    }
}

struct ParagraphView: View {
    @EnvironmentObject private var app: IllumeAppModel
    let paragraph: ReaderParagraph
    let index: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(paragraph.text)
                .font(font)
                .lineSpacing(9 * app.readerSettings.lineHeight)
                .textSelection(.enabled)
                .contentShape(Rectangle())
                .onTapGesture(count: 2) {
                    app.speak(paragraph.text)
                }

            if paragraph.kind != .heading {
                HStack(spacing: 10) {
                    Button {
                        app.speak(paragraph.text)
                    } label: {
                        Label("Speak", systemImage: "play.fill")
                    }
                    .miniReaderButton()

                    Button {
                        Task { await app.generateImage(for: paragraph) }
                    } label: {
                        Label("Image", systemImage: "sparkles")
                    }
                    .miniReaderButton()
                }
                .opacity(0.78)
            }
        }
        .padding(.vertical, paragraph.kind == .heading ? 22 : 2)
    }

    private var font: Font {
        switch paragraph.kind {
        case .heading:
            .system(size: 30 * app.readerSettings.textScale, weight: .black, design: .rounded)
        case .quote:
            .system(size: 20 * app.readerSettings.textScale, weight: .medium, design: .serif).italic()
        default:
            .system(size: 20 * app.readerSettings.textScale, weight: .regular, design: .serif)
        }
    }
}

struct ReaderSettingsSheet: View {
    @EnvironmentObject private var app: IllumeAppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Capsule()
                .fill(.secondary.opacity(0.25))
                .frame(width: 42, height: 5)
                .frame(maxWidth: .infinity)

            Text("Reading")
                .font(.system(.largeTitle, design: .rounded, weight: .black))

            Picker("Theme", selection: $app.readerSettings.theme) {
                ForEach(ReaderThemeChoice.allCases, id: \.self) { theme in
                    Text(theme.rawValue).tag(theme)
                }
            }
            .pickerStyle(.segmented)

            VStack(spacing: 18) {
                SliderRow(label: "Text", value: $app.readerSettings.textScale, range: 0.82...1.42)
                SliderRow(label: "Line", value: $app.readerSettings.lineHeight, range: 1.0...2.0)
                SliderRow(label: "Voice", value: $app.readerSettings.narrationRate, range: 0.35...0.62)
            }

            Picker("Image style", selection: $app.readerSettings.imageStyle) {
                Text("Cartoon").tag(ReaderImageStyle.cartoon)
                Text("Cute").tag(ReaderImageStyle.cute)
            }
            .pickerStyle(.segmented)

            Spacer()
        }
        .padding(24)
        .background(IllumeTheme.paper)
    }
}

struct SliderRow: View {
    let label: String
    @Binding var value: Double
    let range: ClosedRange<Double>

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.system(.subheadline, design: .rounded, weight: .bold))
            Slider(value: $value, in: range)
                .tint(IllumeTheme.accent)
        }
    }
}

struct ReaderImageOverlay: View {
    let url: URL
    let close: () -> Void

    var body: some View {
        VStack {
            Spacer()
            AsyncImage(url: url) { phase in
                switch phase {
                case .success(let image):
                    image
                        .resizable()
                        .scaledToFit()
                case .failure:
                    Image(systemName: "photo")
                        .font(.largeTitle)
                default:
                    ProgressView()
                }
            }
            .frame(maxHeight: 360)
            .padding(12)
            .background(.white, in: RoundedRectangle(cornerRadius: 28, style: .continuous))
            .overlay(alignment: .topTrailing) {
                SoftIconButton(systemName: "xmark", action: close)
                    .padding(16)
            }
            .padding(18)
        }
        .background {
            Color.black.opacity(0.18)
                .ignoresSafeArea()
                .onTapGesture(perform: close)
        }
        .transition(.move(edge: .bottom).combined(with: .opacity))
    }
}

private extension Button {
    @MainActor
    func miniReaderButton() -> some View {
        self
            .font(.system(.caption, design: .rounded, weight: .bold))
            .foregroundStyle(IllumeTheme.ink)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(.white.opacity(0.56), in: Capsule())
            .buttonStyle(.plain)
    }
}
#endif
