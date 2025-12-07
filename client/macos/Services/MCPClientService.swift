import Foundation

enum MCPError: Error {
    case networkError(Error)
    case decodingError(Error)
    case serverError(String)
    case invalidURL
}

class MCPClientService: ObservableObject {
    private let baseURL: URL
    
    init(baseURLString: String = "http://127.0.0.1:6030/mcp") {
        self.baseURL = URL(string: baseURLString)!
    }
    
    /// Execute a tool on the MCP server
    func callTool(name: String, arguments: [String: Any] = [:]) async throws -> String {
        let url = baseURL.appendingPathComponent("call_tool")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let payload: [String: Any] = [
            "name": name,
            "arguments": arguments
        ]
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: payload)
        } catch {
            throw MCPError.networkError(error)
        }
        
        // Debug
        // print("Calling \(name)...")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw MCPError.networkError(NSError(domain: "MCP", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid response"]))
        }
        
        if httpResponse.statusCode != 200 {
            let errorText = String(data: data, encoding: .utf8) ?? "Unknown server error"
            throw MCPError.serverError("Status \(httpResponse.statusCode): \(errorText)")
        }
        
        // FastMCP usually returns JSON like { "content": [{ "type": "text", "text": "result..." }] }
        // OR my server tools return the result string directly in some cases?
        // Let's assume standard MCP response structure or the raw string if simple.
        // My server/main.py tools return `str`. FastMCP wraps this.
        
        // Attempt to parse FastMCP wrapper
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let content = json["content"] as? [[String: Any]],
           let firstText = content.first?["text"] as? String {
            return firstText
        }
        
        // Fallback: Return raw body
        return String(data: data, encoding: .utf8) ?? ""
    }
    
    /// Convenience: Fetch projects as structured objects
    func fetchProjects() async throws -> [ProjectItem] {
        // Call the new JSON tool
        let jsonString = try await callTool(name: "list_projects_json")
        
        guard let data = jsonString.data(using: .utf8) else {
            throw MCPError.decodingError(NSError(domain: "MCP", code: -2, userInfo: [NSLocalizedDescriptionKey: "Invalid JSON from server"]))
        }
        
        do {
            return try JSONDecoder().decode([ProjectItem].self, from: data)
        } catch {
            print("JSON Decode Error: \(error)")
            // Fallback: If JSON fails, maybe it returned "No projects found" text
            return []
        }
    }
}
