import SwiftUI

/// Placeholder notes tab — editorial empty state.
struct NotesView: View {

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Notes")
                    .font(.system(size: 28, weight: .bold))
                    .foregroundStyle(Theme.onSurface)

                Spacer()

                // Disabled + button for now
                Button {} label: {
                    Image(systemName: "plus")
                        .font(.title3.weight(.medium))
                        .foregroundStyle(Theme.onSurfaceVariant.opacity(0.4))
                        .frame(width: 40, height: 40)
                        .background(Theme.surfaceContainerLow)
                        .clipShape(Circle())
                }
                .disabled(true)
            }
            .sectionContainer()
            .padding(.top, 16)

            Spacer()

            // Empty state — editorial feel
            VStack(spacing: 16) {
                Image(systemName: "note.text")
                    .font(.system(size: 48, weight: .light))
                    .foregroundStyle(Theme.onSurfaceVariant.opacity(0.3))

                Text("Your voice notes\nwill live here.")
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(Theme.onSurfaceVariant.opacity(0.5))
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)

                Text("Coming soon")
                    .font(.caption)
                    .foregroundStyle(Theme.onSurfaceVariant.opacity(0.3))
                    .textCase(.uppercase)
                    .tracking(1.5)
            }

            Spacer()
            Spacer()
        }
        .background(Theme.surface)
    }
}

#Preview {
    NotesView()
}
