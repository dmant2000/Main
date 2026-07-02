import SwiftUI
import UIKit
import KindredCore

// Chart palette: validated categorical slots, stepped separately for light and
// dark surfaces. Trend colors are status tokens, never used for series.
extension Color {
    private static func adaptive(light: UInt32, dark: UInt32) -> Color {
        Color(UIColor { traits in
            let rgb = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(
                red: CGFloat((rgb >> 16) & 0xFF) / 255,
                green: CGFloat((rgb >> 8) & 0xFF) / 255,
                blue: CGFloat(rgb & 0xFF) / 255,
                alpha: 1
            )
        })
    }

    static let seriesTexts = adaptive(light: 0x2A78D6, dark: 0x3987E5)
    static let seriesCalls = adaptive(light: 0x1BAF7A, dark: 0x199E70)
    static let trendGood = adaptive(light: 0x006300, dark: 0x0CA30C)
    static let trendBad = adaptive(light: 0xD03B3B, dark: 0xE66767)
}

extension TrendStatus {
    var label: String {
        switch self {
        case .rising: return "Rising"
        case .steady: return "Steady"
        case .fading: return "Fading"
        case .dormant: return "Dormant"
        }
    }

    var icon: String {
        switch self {
        case .rising: return "arrow.up.right"
        case .steady: return "arrow.right"
        case .fading: return "arrow.down.right"
        case .dormant: return "pause"
        }
    }

    var color: Color {
        switch self {
        case .rising: return .trendGood
        case .steady: return .secondary
        case .fading: return .trendBad
        case .dormant: return .secondary
        }
    }
}

enum Formatters {
    static let weekLabel: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "MMM d"
        return f
    }()

    static func delta(_ deltaPct: Double?) -> String? {
        guard let deltaPct else { return nil }
        let pct = Int((deltaPct * 100).rounded())
        return "\(pct >= 0 ? "+" : "")\(pct)% vs prior 8 wks"
    }
}
