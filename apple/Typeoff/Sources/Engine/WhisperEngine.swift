import Foundation
import AVFoundation
import CoreML

/// Local Whisper transcription engine using CoreML.
/// Loads base model (~74MB), runs on Neural Engine.
final class WhisperEngine: ObservableObject {

    @Published var isModelLoaded = false
    @Published var isTranscribing = false

    private var whisperModel: WhisperBase?  // CoreML generated class

    // MARK: - Model lifecycle

    /// Load model — call once at app start or on first use.
    /// Takes ~0.2-0.5s on Neural Engine.
    func loadModel() async {
        guard whisperModel == nil else { return }

        let config = MLModelConfiguration()
        config.computeUnits = .all  // Prefer Neural Engine

        do {
            whisperModel = try await WhisperBase.load(configuration: config)
            await MainActor.run { isModelLoaded = true }
            print("[Typeoff] Model loaded")
        } catch {
            print("[Typeoff] Model load failed: \(error)")
        }
    }

    /// Unload model to free memory when not in use.
    func unloadModel() {
        whisperModel = nil
        isModelLoaded = false
        print("[Typeoff] Model unloaded")
    }

    // MARK: - Transcription

    /// Transcribe audio samples (16kHz mono Float32) → text.
    func transcribe(audioSamples: [Float], sampleRate: Int = 16000) async -> String {
        guard let model = whisperModel else { return "" }

        await MainActor.run { isTranscribing = true }
        defer { Task { @MainActor in isTranscribing = false } }

        let startTime = CFAbsoluteTimeGetCurrent()

        // Convert to MLMultiArray for CoreML input
        let audioArray = try? MLMultiArray(shape: [1, NSNumber(value: audioSamples.count)], dataType: .float32)
        guard let audioArray = audioArray else { return "" }

        for (i, sample) in audioSamples.enumerated() {
            audioArray[i] = NSNumber(value: sample)
        }

        do {
            // Run inference
            let input = WhisperBaseInput(audio: audioArray)
            let output = try await model.prediction(input: input)
            let text = output.text.trimmingCharacters(in: .whitespacesAndNewlines)

            let elapsed = CFAbsoluteTimeGetCurrent() - startTime
            print("[Typeoff] Transcribed in \(String(format: "%.1f", elapsed))s: \"\(text)\"")

            return text
        } catch {
            print("[Typeoff] Transcription failed: \(error)")
            return ""
        }
    }
}
