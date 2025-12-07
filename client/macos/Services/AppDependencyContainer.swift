import Foundation
import SwiftData

@MainActor
class AppDependencyContainer: ObservableObject {
    let mcpService: MCPClientService
    let audioService: AudioCaptureService
    let hotkeyManager: HotkeyManager
    
    // Agent Controller (managed here to stay alive)
    let agentController: AgentWindowController
    
    init() {
        self.mcpService = MCPClientService()
        self.audioService = AudioCaptureService()
        self.hotkeyManager = HotkeyManager()
        
        self.agentController = AgentWindowController()
        
        // Wire up dependencies if needed
        // e.g., hotkeyManager.onHotkeyPress = { agentController.toggle() }
    }
}
