import Foundation

struct MCPTool: Codable, Identifiable {
    var id: String { name }
    let name: String
    let description: String?
    // We can expand this to include input schema if needed
}

struct MCPResult: Codable {
    let result: String?
    let error: String?
}
