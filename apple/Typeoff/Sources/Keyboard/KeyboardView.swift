import SwiftUI

/// Keyboard extension view — placeholder until App Groups are available.
struct KeyboardView: View {

    let onInsertText: (String) -> Void
    let onDeleteBackward: () -> Void
    let onNextKeyboard: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            // Status bar
            Text("Open TypeOff app to use voice transcription")
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color(.secondarySystemBackground))

            // Button row
            HStack(spacing: 16) {
                Button { onNextKeyboard() } label: {
                    Image(systemName: "globe")
                        .font(.title3)
                        .frame(width: 44, height: 44)
                }
                .foregroundStyle(.primary)

                Spacer()

                // Mic button — disabled until App Groups
                ZStack {
                    Circle()
                        .fill(Color.blue.opacity(0.3))
                        .frame(width: 52, height: 52)
                    Image(systemName: "mic.fill")
                        .font(.title2)
                        .foregroundStyle(.white)
                }

                Spacer()

                Button { onDeleteBackward() } label: {
                    Image(systemName: "delete.backward")
                        .font(.title3)
                        .frame(width: 44, height: 44)
                }
                .foregroundStyle(.primary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
        .frame(height: 80)
        .background(Color(.systemBackground))
    }
}
