import SwiftUI

/// Simple voice-to-text test: record → stop → transcribe.
struct NotesView: View {

    @EnvironmentObject var engine: WhisperEngine
    @State private var transcript: String = ""
    @State private var isRecording = false
    @State private var isTranscribing = false
    @State private var recorder = AudioRecorder()

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Notes")
                    .font(.system(size: 28, weight: .bold))
                    .foregroundStyle(Theme.onSurface)

                Spacer()

                if engine.isModelLoaded {
                    Text("Ready")
                        .font(.caption)
                        .foregroundStyle(Theme.success)
                } else if !engine.loadingProgress.isEmpty {
                    Text(engine.loadingProgress)
                        .font(.caption)
                        .foregroundStyle(Theme.onSurfaceVariant)
                } else {
                    Text("No model")
                        .font(.caption)
                        .foregroundStyle(Theme.error)
                }
            }
            .sectionContainer()
            .padding(.top, 16)

            // Transcript
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if transcript.isEmpty && !isRecording && !isTranscribing {
                        Text("Tap the mic to start speaking.\nTap again to stop and transcribe.")
                            .font(.body)
                            .foregroundStyle(Theme.onSurfaceVariant.opacity(0.5))
                            .padding(.top, 40)
                    } else {
                        Text(transcript)
                            .font(.system(size: 17))
                            .foregroundStyle(Theme.onSurface)
                            .textSelection(.enabled)

                        if isRecording {
                            Text("Recording...")
                                .font(.caption)
                                .foregroundStyle(.red)
                        }

                        if isTranscribing {
                            HStack(spacing: 8) {
                                ProgressView()
                                Text("Transcribing...")
                                    .font(.caption)
                                    .foregroundStyle(Theme.onSurfaceVariant)
                            }
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .sectionContainer()
            }

            Spacer()

            // Controls
            HStack(spacing: 20) {
                Button {
                    transcript = ""
                } label: {
                    Image(systemName: "trash")
                        .font(.title3)
                        .frame(width: 44, height: 44)
                        .foregroundStyle(transcript.isEmpty ? Theme.onSurfaceVariant.opacity(0.3) : Theme.error)
                }
                .disabled(transcript.isEmpty)

                Spacer()

                Button { toggleRecording() } label: {
                    ZStack {
                        Circle()
                            .fill(isRecording ? Color.red : (engine.isModelLoaded ? Theme.primary : Theme.primary.opacity(0.3)))
                            .frame(width: 64, height: 64)

                        Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                            .font(.title2)
                            .foregroundStyle(.white)
                    }
                }
                .disabled(!engine.isModelLoaded || isTranscribing)

                Spacer()

                Button {
                    UIPasteboard.general.string = transcript
                } label: {
                    Image(systemName: "doc.on.doc")
                        .font(.title3)
                        .frame(width: 44, height: 44)
                        .foregroundStyle(transcript.isEmpty ? Theme.onSurfaceVariant.opacity(0.3) : Theme.primary)
                }
                .disabled(transcript.isEmpty)
            }
            .sectionContainer()
            .padding(.vertical, 16)
        }
        .background(Theme.surface)
    }

    private func toggleRecording() {
        if isRecording {
            // Stop and transcribe
            let audio = recorder.stop()
            isRecording = false
            isTranscribing = true

            Task {
                let text = await engine.transcribe(audioSamples: audio)
                if !text.isEmpty {
                    transcript += (transcript.isEmpty ? "" : "\n") + text
                }
                isTranscribing = false
            }
        } else {
            // Start recording
            do {
                try recorder.start()
                isRecording = true
            } catch {
                print("[Typeoff] Recorder failed: \(error)")
            }
        }
    }
}

