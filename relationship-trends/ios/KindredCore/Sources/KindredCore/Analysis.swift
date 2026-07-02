import Foundation

/// Relationship trend analysis — a direct port of the web app's analysis.js.
/// Activity is bucketed into calendar weeks (Monday, UTC); each week gets a
/// connection score; the last complete weeks are compared to the weeks before
/// them to classify the relationship as rising / steady / fading / dormant.
public enum Analysis {
    // Score weights: a completed call is worth more than a text, and longer
    // calls count for more. A missed call still shows intent to connect.
    public static let textWeight = 1.0
    public static let callWeight = 6.0
    public static let callMinuteWeight = 0.4
    public static let missedWeight = 1.0

    public static let recentWeeks = 4     // window treated as "now"
    public static let baselineWeeks = 8   // window treated as "how things were"
    public static let trendThreshold = 0.25
    public static let dormantWeeks = 8

    static let dayMs = 24.0 * 60 * 60 * 1000
    static let weekMs = 7 * dayMs
}

public struct WeekStats: Equatable, Sendable {
    public var weekStartMs: Double
    public var texts = 0
    public var calls = 0
    public var missed = 0
    public var callMinutes = 0.0
    public var outgoing = 0
    public var incoming = 0

    public init(weekStartMs: Double) {
        self.weekStartMs = weekStartMs
    }

    public var score: Double {
        Double(texts) * Analysis.textWeight
            + Double(calls) * Analysis.callWeight
            + callMinutes * Analysis.callMinuteWeight
            + Double(missed) * Analysis.missedWeight
    }

    public var weekStart: Date { Date(timeIntervalSince1970: weekStartMs / 1000) }
}

public enum TrendStatus: String, Codable, Sendable {
    case rising, steady, fading, dormant
}

public struct Trend: Equatable, Sendable {
    public var status: TrendStatus
    /// Relative change of the recent window vs the baseline window.
    /// nil when there isn't enough history to compare.
    public var deltaPct: Double?
    public var recentAvg: Double
    public var baselineAvg: Double
}

public struct ContactTotals: Equatable, Sendable {
    public var texts = 0
    public var calls = 0
    public var callMinutes = 0.0
    public var events = 0
}

public struct ContactAnalysis: Identifiable, Sendable {
    public var id: String
    public var name: String
    public var number: String
    public var series: [WeekStats]
    public var trend: Trend
    /// Share of directed events the user initiated; nil with no directed events.
    public var outboundShare: Double?
    public var daysSinceLast: Int
    public var totals: ContactTotals
}

public struct Summary: Equatable, Sendable {
    public var contacts = 0
    public var events = 0
    public var rising = 0
    public var fading = 0
}

/// Strips formatting; drops a leading US country code; keeps the last 10
/// digits of anything longer.
public func normalizeNumber(_ raw: String) -> String {
    let digits = raw.filter(\.isNumber)
    if digits.count == 11 && digits.hasPrefix("1") { return String(digits.dropFirst()) }
    if digits.count > 10 { return String(digits.suffix(10)) }
    return digits
}

public func formatNumber(_ raw: String) -> String {
    let d = normalizeNumber(raw)
    guard d.count == 10 else { return raw.isEmpty ? "Unknown" : raw }
    let a = d.prefix(3)
    let b = d.dropFirst(3).prefix(3)
    let c = d.suffix(4)
    return "(\(a)) \(b)-\(c)"
}

/// Epoch ms of Monday 00:00 UTC of the week containing `ms`.
/// (1970-01-01 was a Thursday — three days after its Monday.)
public func weekStartMs(_ ms: Double) -> Double {
    let days = (ms / Analysis.dayMs).rounded(.down)
    let daysSinceMonday = (days + 3).truncatingRemainder(dividingBy: 7)
    return (days - daysSinceMonday) * Analysis.dayMs
}

/// Contiguous weekly buckets from the first event's week through `nowMs`.
public func weeklySeries(_ events: [CommEvent], nowMs: Double) -> [WeekStats] {
    guard !events.isEmpty else { return [] }
    var byWeek: [Double: WeekStats] = [:]
    var first = Double.infinity
    for e in events {
        let ws = weekStartMs(e.timestampMs)
        first = min(first, ws)
        var w = byWeek[ws] ?? WeekStats(weekStartMs: ws)
        switch (e.kind, e.direction) {
        case (.text, _):
            w.texts += 1
            if e.direction == .outgoing { w.outgoing += 1 } else { w.incoming += 1 }
        case (.call, .missed):
            w.missed += 1
        case (.call, _):
            w.calls += 1
            w.callMinutes += e.durationSec / 60
            if e.direction == .outgoing { w.outgoing += 1 } else { w.incoming += 1 }
        }
        byWeek[ws] = w
    }
    let last = weekStartMs(nowMs)
    var series: [WeekStats] = []
    var ws = first
    while ws <= last {
        var w = byWeek[ws] ?? WeekStats(weekStartMs: ws)
        w.callMinutes = (w.callMinutes * 10).rounded() / 10
        series.append(w)
        ws += Analysis.weekMs
    }
    return series
}

private func average(_ values: ArraySlice<Double>) -> Double {
    values.isEmpty ? 0 : values.reduce(0, +) / Double(values.count)
}

/// Classify a weekly series. The final entry is the current, in-progress week —
/// a partial week always undercounts, so it is excluded from every window.
public func classifyTrend(_ series: [WeekStats]) -> Trend {
    let complete = series.count > 1 ? Array(series.dropLast()) : series
    let scores = complete.map(\.score)
    let n = scores.count

    let recent = scores[max(0, n - Analysis.recentWeeks)...]
    let baselineStart = max(0, n - Analysis.recentWeeks - Analysis.baselineWeeks)
    let baseline = scores[baselineStart..<max(baselineStart, n - Analysis.recentWeeks)]
    let recentAvg = average(recent)
    let baselineAvg = average(baseline)

    if n >= Analysis.dormantWeeks, scores.suffix(Analysis.dormantWeeks).allSatisfy({ $0 == 0 }) {
        return Trend(status: .dormant, deltaPct: -1, recentAvg: recentAvg, baselineAvg: baselineAvg)
    }
    if baseline.isEmpty || baselineAvg == 0 {
        // Not enough history to compare against: a live relationship reads
        // steady; one that just appeared from nothing reads rising.
        let status: TrendStatus = recentAvg > 0 && !baseline.isEmpty ? .rising : .steady
        return Trend(status: status, deltaPct: nil, recentAvg: recentAvg, baselineAvg: baselineAvg)
    }
    let deltaPct = (recentAvg - baselineAvg) / baselineAvg
    var status = TrendStatus.steady
    if deltaPct >= Analysis.trendThreshold { status = .rising }
    else if deltaPct <= -Analysis.trendThreshold { status = .fading }
    return Trend(status: status, deltaPct: deltaPct, recentAvg: recentAvg, baselineAvg: baselineAvg)
}

func displayName(_ events: [CommEvent]) -> String {
    var counts: [String: Int] = [:]
    for e in events where !e.contactName.isEmpty {
        counts[e.contactName, default: 0] += 1
    }
    if let best = counts.max(by: { ($0.value, $1.key) < ($1.value, $0.key) })?.key {
        return best
    }
    return formatNumber(events.first?.number ?? "")
}

public func analyzeContact(_ events: [CommEvent], key: String, nowMs: Double) -> ContactAnalysis {
    let sorted = events.sorted { $0.timestampMs < $1.timestampMs }
    let series = weeklySeries(sorted, nowMs: nowMs)
    let trend = classifyTrend(series)

    var totals = ContactTotals()
    var out = 0
    var directed = 0
    for e in sorted {
        totals.events += 1
        switch (e.kind, e.direction) {
        case (.text, _): totals.texts += 1
        case (.call, .missed): break
        case (.call, _):
            totals.calls += 1
            totals.callMinutes += e.durationSec / 60
        }
        if e.direction == .incoming || e.direction == .outgoing {
            directed += 1
            if e.direction == .outgoing { out += 1 }
        }
    }
    let lastMs = sorted.last?.timestampMs ?? nowMs

    return ContactAnalysis(
        id: key,
        name: displayName(sorted),
        number: sorted.first(where: { !$0.number.isEmpty })?.number ?? "",
        series: series,
        trend: trend,
        outboundShare: directed == 0 ? nil : Double(out) / Double(directed),
        daysSinceLast: max(0, Int((nowMs - lastMs) / Analysis.dayMs)),
        totals: totals
    )
}

public func groupByContact(_ events: [CommEvent]) -> [String: [CommEvent]] {
    var groups: [String: [CommEvent]] = [:]
    for e in events {
        var key = normalizeNumber(e.number)
        if key.isEmpty { key = e.contactName.lowercased() }
        if key.isEmpty { key = "unknown" }
        groups[key, default: []].append(e)
    }
    return groups
}

public func analyzeAll(_ events: [CommEvent], nowMs: Double) -> (contacts: [ContactAnalysis], summary: Summary) {
    var contacts: [ContactAnalysis] = []
    for (key, group) in groupByContact(events) {
        // One-off numbers (verification codes, spam) aren't relationships.
        guard group.count >= 2 else { continue }
        contacts.append(analyzeContact(group, key: key, nowMs: nowMs))
    }
    contacts.sort { ($0.totals.events, $1.name) > ($1.totals.events, $0.name) }
    var summary = Summary()
    summary.contacts = contacts.count
    summary.events = contacts.reduce(0) { $0 + $1.totals.events }
    summary.rising = contacts.filter { $0.trend.status == .rising }.count
    summary.fading = contacts.filter { $0.trend.status == .fading || $0.trend.status == .dormant }.count
    return (contacts, summary)
}
