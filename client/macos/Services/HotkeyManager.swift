import Foundation
import Carbon

class HotkeyManager: ObservableObject {
    
    var onHotkeyPress: (() -> Void)?
    
    init() {
        registerHotkey()
    }
    
    private func registerHotkey() {
        // Simple global hotkey registration for Option+Space (Virtual key 49 + cmdKey/optionKey)
        // Note: Carbon APIs are old but effective. 
        // For a simpler approach in Swift without bridging headers, we usually check NSEvent in Local monitoring
        // or use library like HotKey.
        // For this scaffold, we'll setup a Local Monitor which works when app is active, 
        // global requires Accessibility permissions and EventTap.
        
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            // Check for Option + Space (Space is 49)
            if event.keyCode == 49 && event.modifierFlags.contains(.option) {
                self.onHotkeyPress?()
                return nil // Consume event
            }
            return event
        }
    }
}
