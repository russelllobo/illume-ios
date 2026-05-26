#if os(iOS)
import SwiftUI

enum IllumeTheme {
    static let ink = Color(red: 0.08, green: 0.075, blue: 0.065)
    static let paper = Color(red: 0.985, green: 0.975, blue: 0.945)
    static let mist = Color(red: 0.925, green: 0.94, blue: 0.93)
    static let accent = Color(red: 0.04, green: 0.62, blue: 0.37)
    static let coral = Color(red: 1.0, green: 0.38, blue: 0.28)
    static let plum = Color(red: 0.34, green: 0.22, blue: 0.46)
    static let spring = Animation.spring(response: 0.34, dampingFraction: 0.78)
}

struct PillButtonStyle: ButtonStyle {
    var tint: Color = IllumeTheme.ink
    var foreground: Color = .white

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(.headline, design: .rounded, weight: .semibold))
            .foregroundStyle(foreground)
            .padding(.horizontal, 18)
            .frame(height: 52)
            .frame(maxWidth: .infinity)
            .background(tint, in: Capsule())
            .scaleEffect(configuration.isPressed ? 0.96 : 1)
            .animation(IllumeTheme.spring, value: configuration.isPressed)
    }
}

struct SoftIconButton: View {
    let systemName: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(IllumeTheme.ink)
                .frame(width: 44, height: 44)
                .background(.white.opacity(0.72), in: Circle())
                .overlay(Circle().stroke(.black.opacity(0.06)))
        }
        .buttonStyle(.plain)
    }
}
#endif
