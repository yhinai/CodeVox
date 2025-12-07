import SwiftUI

struct SidebarView: View {
    @EnvironmentObject var mcpService: MCPClientService
    @State private var projects: [ProjectItem] = []
    
    var body: some View {
        List(projects) { project in
            HStack {
                Image(systemName: project.iconName)
                    .foregroundColor(.accentColor)
                VStack(alignment: .leading) {
                    Text(project.name)
                        .font(.headline)
                    if let remote = project.remote {
                        Text(remote)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .padding(.vertical, 4)
        }
        .listStyle(SidebarListStyle())
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button(action: refresh) {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
            }
        }
        .task {
            refresh()
        }
    }
    
    func refresh() {
        Task {
            do {
                projects = try await mcpService.fetchProjects()
            } catch {
                print("Error fetching projects: \(error)")
            }
        }
    }
}
