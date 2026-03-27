import SwiftUI

/// Editorial Fluidity design system — warm whites, indigo primary, tonal depth.
/// No borders. No dividers. Separation through background color shifts only.
enum Theme {

    // MARK: - Colors

    /// The canvas
    static let surface = Color(hex: 0xFAF9FE)
    /// Subtle grouping
    static let surfaceContainerLow = Color(hex: 0xF3F3FA)
    /// Interactive clusters
    static let surfaceContainer = Color(hex: 0xECEDF7)
    /// Highlight
    static let surfaceContainerHighest = Color(hex: 0xDFE2F0)
    /// Card backgrounds
    static let surfaceContainerLowest = Color.white

    /// Primary indigo
    static let primary = Color(hex: 0x005BC1)
    /// Dimmed primary for gradients
    static let primaryDim = Color(hex: 0x004FAA)
    /// Primary container
    static let primaryContainer = Color(hex: 0xD8E2FF)

    /// Text - primary
    static let onSurface = Color(hex: 0x2E323D)
    /// Text - secondary/labels
    static let onSurfaceVariant = Color(hex: 0x5B5F6B)

    /// Error
    static let error = Color(hex: 0x9F403D)

    /// Success green
    static let success = Color(hex: 0x2D8B55)

    // MARK: - Typography helpers

    /// Display large — editorial, magazine-like
    static func displayLarge(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 34, weight: .bold, design: .default))
            .foregroundStyle(onSurface)
    }

    /// Headline — section headers
    static func headline(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 13, weight: .medium))
            .foregroundStyle(onSurfaceVariant)
            .textCase(.uppercase)
            .tracking(0.8)
    }

    // MARK: - Gradients

    static var primaryGradient: LinearGradient {
        LinearGradient(
            colors: [primary, primaryDim],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    // MARK: - Shapes

    /// Standard card radius
    static let cardRadius: CGFloat = 16
    /// Large container radius
    static let containerRadius: CGFloat = 24
    /// Pill/capsule radius
    static let pillRadius: CGFloat = 48
}

// MARK: - Color hex init

extension Color {
    init(hex: UInt, opacity: Double = 1.0) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity
        )
    }
}

// MARK: - View modifiers

extension View {
    /// Tonal card — no borders, background shift only
    func tonalCard(color: Color = Theme.surfaceContainerLowest) -> some View {
        self
            .padding(16)
            .background(color)
            .clipShape(RoundedRectangle(cornerRadius: Theme.cardRadius, style: .continuous))
    }

    /// Section container with tonal background
    func sectionContainer() -> some View {
        self
            .padding(.horizontal, 20)
    }
}
