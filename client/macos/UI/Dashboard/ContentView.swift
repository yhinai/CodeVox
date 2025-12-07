import SwiftUI

struct ContentView: View {
    @StateObject private var mcpService = MCPClientService()
    
    var body: some View {
        NavigationView {
            SidebarView()
            Text("Select a project")
                .font(.largeTitle)
                .foregroundColor(.secondary)
        }
        .environmentObject(mcpService)
    }
}
