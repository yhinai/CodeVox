import Foundation
import AVFoundation

class AudioCaptureService: ObservableObject {
    @Published var isRecording = false
    @Published var audioLevel: Float = 0.0
    
    // Status for UI: "Listening", "Speaking", "Silence"
    @Published var status: String = "Listening"
    
    private let engine = AVAudioEngine()
    private var silenceThreshold: Float = 0.05
    
    func checkPermission() {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized: break
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { _ in }
        default:
            print("Microphone access denied")
        }
    }
    
    func startCapture() {
        checkPermission()
        
        let inputNode = engine.inputNode
        let format = inputNode.outputFormat(forBus: 0)
        
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, time in
            self.processAudio(buffer: buffer)
        }
        
        do {
            try engine.start()
            DispatchQueue.main.async { self.isRecording = true }
        } catch {
            print("Audio Engine Error: \(error)")
        }
    }
    
    func stopCapture() {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        DispatchQueue.main.async {
            self.isRecording = false
            self.audioLevel = 0
            self.status = "Idle"
        }
    }
    
    private func processAudio(buffer: AVAudioPCMBuffer) {
        guard let channelData = buffer.floatChannelData?[0] else { return }
        let frameLength = Int(buffer.frameLength)
        
        // Calculate RMS
        var sum: Float = 0
        for i in 0..<frameLength {
            sum += channelData[i] * channelData[i]
        }
        let rms = sqrt(sum / Float(frameLength))
        
        // Normalize for UI (heuristic)
        let normalized = min(rms * 5.0, 1.0)
        
        DispatchQueue.main.async {
            self.audioLevel = normalized
            
            // Simple VAD logic for UI status
            if normalized > self.silenceThreshold {
                self.status = "Speaking "
            } else {
                self.status = "Silence  "
            }
        }
    }
}
