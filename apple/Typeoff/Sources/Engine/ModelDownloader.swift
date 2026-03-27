import Foundation

/// Downloads our converted Whisper CoreML models from GitHub repo.
@MainActor
final class ModelDownloader: ObservableObject {

    @Published var isDownloading = false
    @Published var progress: Double = 0
    @Published var statusText: String = ""
    @Published var error: String?

    private let baseURL = "https://huggingface.co/Architectds/OAI_Whisper_CoreML_Base/resolve/main"

    private let modelFiles = [
        "AudioEncoder.mlmodelc/coremldata.bin",
        "AudioEncoder.mlmodelc/metadata.json",
        "AudioEncoder.mlmodelc/model.mil",
        "AudioEncoder.mlmodelc/weights/weight.bin",
        "AudioEncoder.mlmodelc/analytics/coremldata.bin",
        "TextDecoder.mlmodelc/coremldata.bin",
        "TextDecoder.mlmodelc/metadata.json",
        "TextDecoder.mlmodelc/model.mil",
        "TextDecoder.mlmodelc/weights/weight.bin",
        "TextDecoder.mlmodelc/analytics/coremldata.bin",
    ]

    /// Download models to Documents/WhisperModels/whisper-base/
    func download() async -> Bool {
        isDownloading = true
        progress = 0
        error = nil
        statusText = "Preparing..."

        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let destDir = docs.appendingPathComponent("WhisperModels/whisper-base")

        do {
            for (i, file) in modelFiles.enumerated() {
                statusText = "Downloading \(file.split(separator: "/").last ?? "...")..."
                progress = Double(i) / Double(modelFiles.count)

                let url = URL(string: "\(baseURL)/\(file)")!
                let localPath = destDir.appendingPathComponent(file)

                // Skip if already downloaded
                if FileManager.default.fileExists(atPath: localPath.path) {
                    continue
                }

                try FileManager.default.createDirectory(
                    at: localPath.deletingLastPathComponent(),
                    withIntermediateDirectories: true
                )

                let (tempURL, response) = try await URLSession.shared.download(from: url)

                guard let httpResponse = response as? HTTPURLResponse,
                      httpResponse.statusCode == 200 else {
                    throw DownloadError.failed(file)
                }

                try FileManager.default.moveItem(at: tempURL, to: localPath)
            }

            progress = 1.0
            statusText = "Ready"
            isDownloading = false
            return true

        } catch {
            self.error = error.localizedDescription
            statusText = "Download failed"
            isDownloading = false
            return false
        }
    }

    /// Check if models are already downloaded.
    static var isModelDownloaded: Bool {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let encoder = docs.appendingPathComponent("WhisperModels/whisper-base/AudioEncoder.mlmodelc/weights/weight.bin")
        let decoder = docs.appendingPathComponent("WhisperModels/whisper-base/TextDecoder.mlmodelc/weights/weight.bin")
        return FileManager.default.fileExists(atPath: encoder.path)
            && FileManager.default.fileExists(atPath: decoder.path)
    }

    enum DownloadError: LocalizedError {
        case failed(String)
        var errorDescription: String? {
            switch self {
            case .failed(let file): "Failed to download \(file)"
            }
        }
    }
}
