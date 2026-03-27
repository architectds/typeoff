import Foundation
import CoreML

/// Local Whisper transcription engine — raw CoreML, no dependencies.
@MainActor
final class WhisperEngine: ObservableObject {

    @Published var isModelLoaded = false
    @Published var isTranscribing = false
    @Published var loadingProgress: String = ""

    private let pipeline = WhisperPipeline()

    init(modelVariant: String = "base") {}

    // MARK: - Model lifecycle

    func loadModel() async {
        guard !pipeline.isLoaded else {
            isModelLoaded = true
            return
        }

        let modelDir = Self.bundledModelDirectory()
        guard let modelDir = modelDir else {
            loadingProgress = "No model found"
            print("[Typeoff] No bundled model found")
            return
        }

        // Verify files exist
        let encoderPath = modelDir.appendingPathComponent("AudioEncoder.mlmodelc").path
        let decoderPath = modelDir.appendingPathComponent("TextDecoder.mlmodelc").path
        guard FileManager.default.fileExists(atPath: encoderPath),
              FileManager.default.fileExists(atPath: decoderPath) else {
            loadingProgress = "Model files missing"
            print("[Typeoff] Model files missing at \(modelDir.path)")
            return
        }

        loadingProgress = "Loading model..."
        print("[Typeoff] Loading model from \(modelDir.path)")

        do {
            try await pipeline.load(modelDir: modelDir)
            isModelLoaded = true
            loadingProgress = ""
            print("[Typeoff] Engine ready")
        } catch {
            loadingProgress = "Failed to load"
            print("[Typeoff] Load failed: \(error)")
        }
    }

    func unloadModel() {
        pipeline.unload()
        isModelLoaded = false
    }

    // MARK: - Transcription

    func transcribe(audioSamples: [Float]) async -> String {
        guard pipeline.isLoaded else { return "" }

        isTranscribing = true
        defer { isTranscribing = false }

        let startTime = CFAbsoluteTimeGetCurrent()
        let text = await pipeline.transcribe(audioSamples: audioSamples)
        let elapsed = CFAbsoluteTimeGetCurrent() - startTime

        print("[Typeoff] \(String(format: "%.2f", elapsed))s: \"\(text.prefix(80))\"")
        return text
    }

    // MARK: - Model directory

    private static func bundledModelDirectory() -> URL? {
        // Check app bundle resources
        if let resourcePath = Bundle.main.resourcePath {
            let bundleModels = URL(fileURLWithPath: resourcePath)
                .appendingPathComponent("WhisperModels")
                .appendingPathComponent("whisper-base")
            if FileManager.default.fileExists(atPath: bundleModels.path) {
                return bundleModels
            }
        }

        // Fallback: check Documents
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let docsModels = docs.appendingPathComponent("WhisperModels").appendingPathComponent("whisper-base")
        if FileManager.default.fileExists(atPath: docsModels.path) {
            return docsModels
        }

        return nil
    }
}
