import SwiftUI
import AppKit

class AgentWindowController: ObservableObject {
    private var window: NSWindow?
    @Published var isVisible = false
    
    init() {
        setupWindow()
    }
    
    private func setupWindow() {
        // Create a borderless, floating window
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 300, height: 300),
            styleMask: [.borderless, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        
        window.level = .floating
        window.backgroundColor = .clear
        window.isOpaque = false
        window.hasShadow = false // We might draw our own shadow or use standard
        
        // Center it (approx)
        if let screen = NSScreen.main {
            let frame = screen.visibleFrame
            let x = frame.midX - 150
            let y = frame.midY - 150
            window.setFrameOrigin(NSPoint(x: x, y: y))
        }
        
        // Hosting Controller with the Agent View
        let hosting = NSHostingController(rootView: AgentFloatingView())
        window.contentViewController = hosting
        
        // Allow clicking through transparent parts? 
        // For now, keep it simple.
        window.isMovableByWindowBackground = true
        
        self.window = window
    }
    
    func toggle() {
        guard let window = window else { return }
        
        if isVisible {
            window.orderOut(nil)
            isVisible = false
        } else {
            window.makeKeyAndOrderFront(nil)
            isVisible = true
        }
    }
    
    func show() {
        window?.makeKeyAndOrderFront(nil)
        isVisible = true
    }
}
