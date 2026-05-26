#if os(iOS)
import AuthenticationServices
import IllumeCore
import SwiftUI
import UIKit
import UniformTypeIdentifiers

struct RootView: View {
    @EnvironmentObject private var app: IllumeAppModel

    var body: some View {
        ZStack {
            IllumeTheme.paper.ignoresSafeArea()

            if app.isSignedIn {
                LibraryShell()
                    .transition(.scale(scale: 0.98).combined(with: .opacity))
            } else {
                AuthView()
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }

            if app.isLoading || app.isImporting {
                LoadingVeil(text: app.isImporting ? "Importing" : "Syncing")
            }
        }
        .animation(IllumeTheme.spring, value: app.isSignedIn)
    }
}

struct AuthView: View {
    @EnvironmentObject private var app: IllumeAppModel
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            Spacer(minLength: 32)

            VStack(alignment: .leading, spacing: 10) {
                Text("Illume")
                    .font(.system(size: 56, weight: .black, design: .rounded))
                    .foregroundStyle(IllumeTheme.ink)
                Text("Your books, synced and quietly alive.")
                    .font(.system(.title3, design: .rounded, weight: .medium))
                    .foregroundStyle(.secondary)
            }

            VStack(spacing: 14) {
                TextField("Email", text: $email)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .illumeField()

                SecureField("Password", text: $password)
                    .textContentType(app.authMode == .signIn ? .password : .newPassword)
                    .illumeField()
            }

            VStack(spacing: 12) {
                Button(app.authMode == .signIn ? "Sign in" : "Create account") {
                    Task { await app.authenticate(email: email, password: password) }
                }
                .buttonStyle(PillButtonStyle(tint: IllumeTheme.ink))
                .disabled(email.isEmpty || password.count < 6)

                Button {
                    Task { await app.signInWithApple() }
                } label: {
                    Label("Continue with Apple", systemImage: "apple.logo")
                }
                .buttonStyle(PillButtonStyle(tint: .black))

                Button {
                    Task { await app.signInWithGoogle() }
                } label: {
                    Label {
                        Text("Continue with Google")
                    } icon: {
                        Text("G")
                            .font(.system(.body, design: .rounded, weight: .black))
                    }
                }
                .buttonStyle(PillButtonStyle(tint: IllumeTheme.coral))

                Button(app.authMode == .signIn ? "New here? Create an account" : "Already have an account? Sign in") {
                    withAnimation(IllumeTheme.spring) {
                        app.authMode = app.authMode == .signIn ? .signUp : .signIn
                    }
                }
                .font(.system(.subheadline, design: .rounded, weight: .semibold))
                .foregroundStyle(IllumeTheme.ink)
            }

            if !app.notice.isEmpty {
                Text(app.notice)
                    .font(.footnote)
                    .foregroundStyle(IllumeTheme.coral)
                    .transition(.opacity)
            }

            Spacer(minLength: 16)
        }
        .padding(24)
    }
}

struct LibraryShell: View {
    @EnvironmentObject private var app: IllumeAppModel
    @State private var importerOpen = false
    @State private var profileOpen = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 26) {
                    LibraryHeader(profileOpen: $profileOpen, importerOpen: $importerOpen)

                    if app.books.isEmpty {
                        EmptyLibrary(importerOpen: $importerOpen)
                    } else {
                        ContinueSection()
                        BookGrid()
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 18)
                .padding(.bottom, 32)
            }
            .scrollIndicators(.hidden)
            .background(IllumeTheme.paper)
            .refreshable {
                await app.reload()
            }
            .fileImporter(
                isPresented: $importerOpen,
                allowedContentTypes: [.illumeEpub, .pdf],
                allowsMultipleSelection: false
            ) { result in
                guard case .success(let urls) = result, let url = urls.first else { return }
                Task { await app.importDocument(from: url) }
            }
            .sheet(isPresented: $profileOpen) {
                ProfileSheet()
                    .presentationDetents([.medium, .large])
                    .presentationCornerRadius(30)
            }
            .fullScreenCover(item: Binding(
                get: { app.activeBook.map { ActiveReader(id: app.activeBookRow?.id ?? UUID(), book: $0) } },
                set: { if $0 == nil { app.closeReader() } }
            )) { _ in
                ReaderView()
            }
        }
    }
}

struct ActiveReader: Identifiable {
    let id: UUID
    let book: ReaderBook
}

struct LibraryHeader: View {
    @EnvironmentObject private var app: IllumeAppModel
    @Binding var profileOpen: Bool
    @Binding var importerOpen: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Illume")
                        .font(.system(size: 38, weight: .black, design: .rounded))
                    Text("\(app.books.count) books · \(app.imageUsageCount)/\(app.imageLimit) images")
                        .font(.system(.subheadline, design: .rounded, weight: .medium))
                        .foregroundStyle(.secondary)
                }
                Spacer()
                SoftIconButton(systemName: "person.crop.circle") { profileOpen = true }
                SoftIconButton(systemName: "plus") { importerOpen = true }
            }

            if let first = app.books.first {
                Button {
                    Task { await app.open(first) }
                } label: {
                    HStack(spacing: 16) {
                        CoverView(book: first, size: CGSize(width: 86, height: 124))
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Continue")
                                .font(.system(.subheadline, design: .rounded, weight: .bold))
                                .foregroundStyle(IllumeTheme.accent)
                            Text(first.title)
                                .font(.system(.title3, design: .rounded, weight: .bold))
                                .foregroundStyle(IllumeTheme.ink)
                                .lineLimit(2)
                            Text(first.author.isEmpty ? first.fileName : first.author)
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: "arrow.up.right")
                            .font(.headline.weight(.bold))
                            .foregroundStyle(IllumeTheme.ink)
                    }
                    .padding(16)
                    .background(.white.opacity(0.58), in: RoundedRectangle(cornerRadius: 26, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 26).stroke(.black.opacity(0.05)))
                }
                .buttonStyle(.plain)
            }
        }
    }
}

struct ContinueSection: View {
    @EnvironmentObject private var app: IllumeAppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent")
                .font(.system(.title2, design: .rounded, weight: .black))
            ScrollView(.horizontal) {
                HStack(spacing: 16) {
                    ForEach(app.books.prefix(8)) { book in
                        Button {
                            Task { await app.open(book) }
                        } label: {
                            VStack(alignment: .leading, spacing: 10) {
                                CoverView(book: book, size: CGSize(width: 118, height: 170))
                                Text(book.title)
                                    .font(.system(.subheadline, design: .rounded, weight: .bold))
                                    .foregroundStyle(IllumeTheme.ink)
                                    .lineLimit(2)
                                    .frame(width: 118, alignment: .leading)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.vertical, 2)
            }
            .scrollIndicators(.hidden)
        }
    }
}

struct BookGrid: View {
    @EnvironmentObject private var app: IllumeAppModel
    private let columns = [GridItem(.adaptive(minimum: 152), spacing: 18)]

    var body: some View {
        LazyVGrid(columns: columns, alignment: .leading, spacing: 18) {
            ForEach(app.books) { book in
                Button {
                    Task { await app.open(book) }
                } label: {
                    HStack(spacing: 12) {
                        CoverView(book: book, size: CGSize(width: 58, height: 82))
                        VStack(alignment: .leading, spacing: 5) {
                            Text(book.title)
                                .font(.system(.subheadline, design: .rounded, weight: .bold))
                                .foregroundStyle(IllumeTheme.ink)
                                .lineLimit(2)
                            Text(book.documentType.rawValue.uppercased())
                                .font(.caption2.weight(.black))
                                .foregroundStyle(.secondary)
                        }
                        Spacer(minLength: 0)
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.white.opacity(0.5), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                }
                .buttonStyle(.plain)
            }
        }
    }
}

struct EmptyLibrary: View {
    @Binding var importerOpen: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            Image(systemName: "books.vertical.fill")
                .font(.system(size: 54, weight: .bold))
                .foregroundStyle(IllumeTheme.accent)
            Text("Drop in your first book.")
                .font(.system(.largeTitle, design: .rounded, weight: .black))
            Text("EPUBs and PDFs sync through the same private backend as the web app.")
                .font(.system(.body, design: .rounded))
                .foregroundStyle(.secondary)
            Button("Import EPUB or PDF") { importerOpen = true }
                .buttonStyle(PillButtonStyle(tint: IllumeTheme.accent))
        }
        .padding(.top, 60)
    }
}

struct CoverView: View {
    let book: BookRow
    let size: CGSize

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            if let coverUrl = book.coverUrl, !coverUrl.isEmpty {
                CoverArtwork(urlString: coverUrl)
            } else {
                fallbackCover
            }
        }
        .frame(width: size.width, height: size.height)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .shadow(color: .black.opacity(0.14), radius: 12, y: 8)
    }

    private var fallbackCover: some View {
        ZStack(alignment: .bottomLeading) {
            LinearGradient(
                colors: coverColors,
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            Text(book.title.prefix(1))
                .font(.system(size: size.width * 0.46, weight: .black, design: .rounded))
                .foregroundStyle(.white.opacity(0.9))
                .padding(10)
        }
    }

    private var coverColors: [Color] {
        let palettes: [[Color]] = [
            [IllumeTheme.ink, IllumeTheme.accent],
            [IllumeTheme.plum, IllumeTheme.coral],
            [Color(red: 0.08, green: 0.23, blue: 0.26), Color(red: 0.97, green: 0.74, blue: 0.26)]
        ]
        return palettes[abs(book.title.hashValue) % palettes.count]
    }
}

struct CoverArtwork: View {
    let urlString: String

    var body: some View {
        if let image = dataURLImage {
            Image(uiImage: image)
                .resizable()
                .scaledToFill()
        } else if let url = URL(string: urlString) {
            AsyncImage(url: url) { phase in
                switch phase {
                case .success(let image):
                    image
                        .resizable()
                        .scaledToFill()
                default:
                    Rectangle()
                        .fill(.black.opacity(0.08))
                }
            }
        } else {
            Rectangle()
                .fill(.black.opacity(0.08))
        }
    }

    private var dataURLImage: UIImage? {
        guard let commaIndex = urlString.firstIndex(of: ","),
              urlString[..<commaIndex].contains(";base64") else {
            return nil
        }
        let base64 = urlString[urlString.index(after: commaIndex)...]
        guard let data = Data(base64Encoded: String(base64)) else {
            return nil
        }
        return UIImage(data: data)
    }
}

struct ProfileSheet: View {
    @EnvironmentObject private var app: IllumeAppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Capsule()
                .fill(.secondary.opacity(0.25))
                .frame(width: 42, height: 5)
                .frame(maxWidth: .infinity)

            VStack(alignment: .leading, spacing: 6) {
                Text(app.isPro ? "Illume Pro" : "Free plan")
                    .font(.system(.largeTitle, design: .rounded, weight: .black))
                Text(app.session?.user.email ?? "Signed in")
                    .foregroundStyle(.secondary)
            }

            VStack(spacing: 16) {
                Meter(label: "Storage", value: Double(app.storageUsed), max: Double(SupabaseConfig().storageQuotaBytes))
                Meter(label: "Reader images", value: Double(app.imageUsageCount), max: Double(app.imageLimit))
            }

            if app.isPro {
                Button("Restore purchases") {
                    Task { await app.restorePro() }
                }
                .buttonStyle(PillButtonStyle(tint: IllumeTheme.accent))
            } else {
                Button("Go Pro") {
                    Task { await app.purchasePro() }
                }
                .buttonStyle(PillButtonStyle(tint: IllumeTheme.ink))
            }

            Button("Sign out", role: .destructive) {
                app.signOut()
            }
            .buttonStyle(PillButtonStyle(tint: IllumeTheme.coral))

            Spacer()
        }
        .padding(24)
        .background(IllumeTheme.paper)
    }
}

struct Meter: View {
    let label: String
    let value: Double
    let max: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(label).font(.system(.subheadline, design: .rounded, weight: .bold))
                Spacer()
                Text("\(Int(value)) / \(Int(max))")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            GeometryReader { proxy in
                RoundedRectangle(cornerRadius: 6)
                    .fill(.black.opacity(0.08))
                    .overlay(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 6)
                            .fill(IllumeTheme.accent)
                            .frame(width: proxy.size.width * min(1, value / max))
                    }
            }
            .frame(height: 10)
        }
    }
}

struct LoadingVeil: View {
    let text: String

    var body: some View {
        VStack(spacing: 14) {
            ProgressView()
                .controlSize(.large)
            Text(text)
                .font(.system(.headline, design: .rounded, weight: .bold))
        }
        .padding(22)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 26, style: .continuous))
    }
}

private extension View {
    func illumeField() -> some View {
        self
            .font(.system(.body, design: .rounded, weight: .medium))
            .padding(.horizontal, 16)
            .frame(height: 54)
            .background(.white.opacity(0.66), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 18).stroke(.black.opacity(0.06)))
    }
}

private extension UTType {
    static let illumeEpub = UTType(filenameExtension: "epub") ?? .data
}
#endif
