import Foundation

/// Whisper BPE tokenizer — decodes token IDs to text.
/// Loads vocab.json (bundled in app) for ID → string mapping.
///
/// Special tokens:
///   SOT (50258), EOT (50257), Transcribe (50359), Translate (50358)
///   Language tokens: en (50259), zh (50260), es (50262), etc.
final class WhisperTokenizer {

    // Special token IDs
    static let sot: Int32 = 50258           // <|startoftranscript|>
    static let eot: Int32 = 50257           // <|endoftranscript|>
    static let transcribe: Int32 = 50359    // <|transcribe|>
    static let translate: Int32 = 50358     // <|translate|>
    static let noSpeech: Int32 = 50362      // <|nospeech|>
    static let noTimestamps: Int32 = 50363  // <|notimestamps|>

    // Language tokens (50259 = en, 50260 = zh, etc.)
    static let languageTokenBase: Int32 = 50259

    static let languages: [String: Int32] = [
        "en": 50259, "zh": 50260, "de": 50261, "es": 50262, "ru": 50263,
        "ko": 50264, "fr": 50265, "ja": 50266, "pt": 50267, "tr": 50268,
        "pl": 50269, "nl": 50271, "ar": 50272, "it": 50274,
    ]

    private var idToToken: [Int32: String] = [:]
    private var isLoaded = false

    // Byte decoder: maps Whisper's byte-level tokens back to UTF-8
    private let byteDecoder: [Character: UInt8]

    init() {
        // Build byte decoder (reverse of GPT-2 byte encoder)
        var decoder: [Character: UInt8] = [:]
        var byteList: [UInt8] = []

        // Printable ASCII ranges
        for b in UInt8(33)...UInt8(126) { byteList.append(b) }  // ! to ~
        for b in UInt8(161)...UInt8(172) { byteList.append(b) }  // ¡ to ¬
        for b in UInt8(174)...UInt8(255) { byteList.append(b) }  // ® to ÿ

        var n = 0
        for b: UInt8 in 0...255 {
            if !byteList.contains(b) {
                byteList.append(b)
                decoder[Character(Unicode.Scalar(256 + n)!)] = b
                n += 1
            }
        }

        // Map the printable bytes
        for b in byteList.prefix(byteList.count - n) {
            decoder[Character(Unicode.Scalar(b))] = b
        }

        byteDecoder = decoder
    }

    /// Load vocab.json from app bundle.
    func load() {
        guard !isLoaded else { return }

        // Try multiple paths to find vocab.json
        var url = Bundle.main.url(forResource: "vocab", withExtension: "json")

        // Fallback: check inside Resources directory
        if url == nil, let resourcePath = Bundle.main.resourcePath {
            let fallback = URL(fileURLWithPath: resourcePath).appendingPathComponent("vocab.json")
            if FileManager.default.fileExists(atPath: fallback.path) {
                url = fallback
            }
        }

        guard let url = url else {
            print("[Typeoff] vocab.json not found in bundle")
            print("[Typeoff] Bundle path: \(Bundle.main.bundlePath)")
            return
        }

        guard let data = try? Data(contentsOf: url) else {
            print("[Typeoff] Failed to read vocab.json")
            return
        }

        guard let vocab = try? JSONSerialization.jsonObject(with: data) as? [String: Int] else {
            print("[Typeoff] Failed to parse vocab.json")
            return
        }

        // Invert: token string → ID becomes ID → token string
        for (token, id) in vocab {
            idToToken[Int32(id)] = token
        }

        isLoaded = true
        print("[Typeoff] Tokenizer loaded: \(idToToken.count) tokens")
    }

    /// Decode token IDs to text string.
    func decode(_ tokenIds: [Int32]) -> String {
        if !isLoaded {
            print("[Typeoff] Tokenizer not loaded — loading now")
            load()
        }

        if idToToken.isEmpty {
            print("[Typeoff] ERROR: vocab is empty, cannot decode")
            return ""
        }

        var bytes: [UInt8] = []
        var skippedSpecial = 0
        var skippedUnknown = 0
        var decoded = 0

        for id in tokenIds {
            // Skip special tokens
            if id >= WhisperTokenizer.eot { skippedSpecial += 1; continue }

            guard let token = idToToken[id] else { skippedUnknown += 1; continue }
            decoded += 1

            // Convert each character through byte decoder
            for char in token {
                if let byte = byteDecoder[char] {
                    bytes.append(byte)
                } else if let ascii = char.asciiValue {
                    bytes.append(ascii)
                }
            }
        }

        print("[Typeoff] Decode: \(tokenIds.count) tokens → \(decoded) decoded, \(skippedSpecial) special, \(skippedUnknown) unknown, \(bytes.count) bytes")

        // Log first few token IDs for debugging
        if decoded == 0 && !tokenIds.isEmpty {
            let sample = tokenIds.prefix(10).map { String($0) }.joined(separator: ", ")
            print("[Typeoff] First 10 token IDs: [\(sample)]")
        }

        return String(bytes: bytes, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    /// Get initial token sequence for transcription.
    func initialTokens(language: String? = nil) -> [Int32] {
        var tokens: [Int32] = [WhisperTokenizer.sot]

        if let lang = language, let langToken = WhisperTokenizer.languages[lang] {
            tokens.append(langToken)
        }

        tokens.append(WhisperTokenizer.transcribe)
        tokens.append(WhisperTokenizer.noTimestamps)

        return tokens
    }
}
