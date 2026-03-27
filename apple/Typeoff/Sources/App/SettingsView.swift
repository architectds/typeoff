import SwiftUI

struct SettingsView: View {

    @EnvironmentObject var trialManager: TrialManager
    @EnvironmentObject var storeManager: StoreManager
    @EnvironmentObject var engine: WhisperEngine

    @AppStorage("silenceDuration")
    private var silenceDuration: Double = 5.0

    var body: some View {
        ScrollView {
            VStack(spacing: 32) {
                // Header
                VStack(spacing: 4) {
                    Text("Settings")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundStyle(Theme.onSurface)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .sectionContainer()
                .padding(.top, 16)

                // Keyboard setup
                keyboardSection

                // Transcription
                transcriptionSection

                Spacer(minLength: 40)
            }
        }
        .background(Theme.surface)
    }

    // MARK: - Keyboard

    private var keyboardSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Theme.headline("KEYBOARD")
                .padding(.leading, 4)

            VStack(spacing: 0) {
                Link(destination: URL(string: UIApplication.openSettingsURLString)!) {
                    HStack {
                        Image(systemName: "keyboard")
                            .font(.body)
                            .foregroundStyle(Theme.primary)
                            .frame(width: 32)

                        Text("Enable TypeOff Keyboard")
                            .font(.body)
                            .foregroundStyle(Theme.onSurface)

                        Spacer()

                        Image(systemName: "arrow.up.forward")
                            .font(.caption)
                            .foregroundStyle(Theme.onSurfaceVariant)
                    }
                    .padding(16)
                }

                Text("Settings → General → Keyboard → Keyboards → Add New Keyboard → TypeOff")
                    .font(.caption)
                    .foregroundStyle(Theme.onSurfaceVariant)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 16)
            }
            .background(Theme.surfaceContainerLowest)
            .clipShape(RoundedRectangle(cornerRadius: Theme.cardRadius, style: .continuous))
        }
        .sectionContainer()
    }

    // MARK: - Transcription

    private var transcriptionSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Theme.headline("TRANSCRIPTION")
                .padding(.leading, 4)

            VStack(spacing: 0) {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Silence timeout")
                            .font(.body)
                            .foregroundStyle(Theme.onSurface)
                        Spacer()
                        Text("\(Int(silenceDuration))s")
                            .font(.body.monospacedDigit())
                            .foregroundStyle(Theme.onSurfaceVariant)
                    }

                    Slider(value: $silenceDuration, in: 3...15, step: 1)
                        .tint(Theme.primary)
                }
                .padding(16)
            }
            .background(Theme.surfaceContainerLowest)
            .clipShape(RoundedRectangle(cornerRadius: Theme.cardRadius, style: .continuous))
        }
        .sectionContainer()
    }
}

