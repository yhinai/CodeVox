import SwiftUI

struct AgentAvatarView: View {
    @ObservedObject var audioService: AudioCaptureService
    
    var body: some View {
        ZStack {
            // Background Glow
            Circle()
                .fill(
                    RadialGradient(
                        gradient: Gradient(colors: [colorForStatus.opacity(0.6), .clear]),
                        center: .center,
                        startRadius: 0,
                        endRadius: 100
                    )
                )
                .frame(width: 200, height: 200)
                .scaleEffect(1.0 + CGFloat(audioService.audioLevel) * 0.5)
                .animation(.spring(response: 0.2, dampingFraction: 0.5), value: audioService.audioLevel)
            
            // Core Orb
            Circle()
                .fill(colorForStatus)
                .frame(width: 80, height: 80)
                .shadow(color: colorForStatus.opacity(0.8), radius: 20, x: 0, y: 0)
                .scaleEffect(1.0 + CGFloat(audioService.audioLevel) * 0.2)
            
            // Icon
            Image(systemName: "sparkles")
                .font(.system(size: 30))
                .foregroundColor(.white)
        }
    }
    
    var colorForStatus: Color {
        // "Listening", "Speaking ", "Silence  "
        let s = audioService.status.trimmingCharacters(in: .whitespaces)
        switch s {
        case "Speaking": return .blue
        case "Listening": return .orange
        case "Silence": return .purple
        default: return .gray
        }
    }
}
