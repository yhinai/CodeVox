import SwiftUI

struct ProjectDetailView: View {
    let project: ProjectItem
    @EnvironmentObject var mcpService: MCPClientService
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack {
                Image(systemName: project.iconName)
                    .font(.system(size: 48))
                
                VStack(alignment: .leading) {
                    Text(project.name)
                        .font(.largeTitle)
                        .bold()
                    
                    Text(project.path)
                        .font(.title3)
                        .foregroundColor(.secondary)
                }
            }
            .padding()
            
            Divider()
            
            Text("Description")
                .font(.headline)
            
            Text(project.description ?? "No description available.")
                .font(.body)
                .foregroundColor(.secondary)
            
            Spacer()
            
            HStack {
                Button(action: {
                    Task { try? await mcpService.callTool(name: "run_in_project", arguments: ["project_name": project.name, "command": "run"]) }
                }) {
                    Label("Run Suggested Command", systemImage: "play.fill")
                        .padding()
                }
                .buttonStyle(.borderedProminent)
                
                Button(action: {
                    Task { try? await mcpService.callTool(name: "run_shell", arguments: ["command": "code .", "cwd": project.path]) }
                }) {
                    Label("Open in VS Code", systemImage: "hammer.fill")
                        .padding()
                }
            }
            .padding()
        }
        .frame(minWidth: 400, minHeight: 400)
    }
}
