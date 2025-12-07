import Foundation

enum ProjectType: String, Codable {
    case python
    case node
    case rust
    case unknown
}

struct ProjectItem: Codable, Identifiable {
    var id: String { path }
    let name: String
    let path: String
    let type: String
    let description: String?
    let remote: String?
    
    // Computed property for icon name (SF Symbol)
    var iconName: String {
        switch type.lowercased() {
        case "python": return "curlybraces"
        case "node": return "hexagon"
        case "rust": return "gear"
        default: return "folder"
        }
    }
}
