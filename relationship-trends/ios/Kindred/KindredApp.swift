import SwiftUI

@main
struct KindredApp: App {
    @StateObject private var store = DataStore()

    var body: some Scene {
        WindowGroup {
            DashboardView()
                .environmentObject(store)
        }
    }
}
