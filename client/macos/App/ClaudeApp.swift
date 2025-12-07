import SwiftUI

@main
struct ClaudeApp: App {
    @StateObject var container = AppDependencyContainer()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(container.mcpService)
        }
        .commands {
            SidebarCommands()
        }
        
        // Settings Window
        Settings {
            Text("Settings Placeholder")
        }
    }
}
