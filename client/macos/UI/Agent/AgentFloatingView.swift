import SwiftUI

struct AgentFloatingView: View {
    // Ideally injected via EnvironmentObject
    @StateObject var audioService = AudioCaptureService() 
    
    var body: some View {
        VStack {
            AgentAvatarView(audioService: audioService)
            
            // Transcription Bubble
            if !audioService.status.isEmpty {
                Text(audioService.status)
                    .font(.caption)
                    .padding(8)
                    .background(.ultraThinMaterial)
                    .cornerRadius(12)
                    .padding(.top, -20)
            }
        }
        .frame(width: 300, height: 300)
        .onAppear {
            audioService.startCapture()
        }
    }
}
