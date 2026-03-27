import Foundation
import AVFoundation

/// Simple audio recorder — records to a buffer, returns samples on stop.
final class AudioRecorder {

    private let sampleRate: Double = 16000
    private var audioEngine: AVAudioEngine?
    private var buffer: [Float] = []
    private let bufferLock = NSLock()

    func start() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.record, mode: .measurement)
        try session.setActive(true)

        audioEngine = AVAudioEngine()
        guard let engine = audioEngine else { return }

        let inputNode = engine.inputNode
        let hwFormat = inputNode.outputFormat(forBus: 0)

        let targetFormat = AVAudioFormat(commonFormat: .pcmFormatFloat32,
                                         sampleRate: sampleRate,
                                         channels: 1,
                                         interleaved: false)!

        let converter = AVAudioConverter(from: hwFormat, to: targetFormat)

        inputNode.installTap(onBus: 0, bufferSize: 4800, format: hwFormat) { [weak self] pcmBuffer, _ in
            guard let self = self, let converter = converter else { return }

            let frameCapacity = AVAudioFrameCount(Double(pcmBuffer.frameLength) * self.sampleRate / hwFormat.sampleRate)
            guard frameCapacity > 0,
                  let convertedBuffer = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: frameCapacity) else { return }

            var error: NSError?
            var consumed = false
            converter.convert(to: convertedBuffer, error: &error) { _, outStatus in
                if consumed { outStatus.pointee = .noDataNow; return nil }
                consumed = true
                outStatus.pointee = .haveData
                return pcmBuffer
            }

            guard error == nil,
                  let channelData = convertedBuffer.floatChannelData?[0] else { return }

            let frameCount = Int(convertedBuffer.frameLength)
            let samples = Array(UnsafeBufferPointer(start: channelData, count: frameCount))

            self.bufferLock.lock()
            self.buffer.append(contentsOf: samples)
            self.bufferLock.unlock()
        }

        bufferLock.lock()
        buffer = []
        bufferLock.unlock()

        try engine.start()
        print("[Typeoff] Recording started")
    }

    func stop() -> [Float] {
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil

        bufferLock.lock()
        let audio = buffer
        buffer = []
        bufferLock.unlock()

        print("[Typeoff] Recording stopped: \(String(format: "%.1f", Double(audio.count) / sampleRate))s")
        return audio
    }
}
