import XCTest
@testable import KindredCore

final class AnalysisTests: XCTestCase {
    private let weekMs = 7 * 24 * 60 * 60 * 1000.0
    private let dayMs = 24 * 60 * 60 * 1000.0

    private func utcMs(_ year: Int, _ month: Int, _ day: Int, hour: Int = 0) -> Double {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "UTC")!
        let comps = DateComponents(year: year, month: month, day: day, hour: hour)
        return cal.date(from: comps)!.timeIntervalSince1970 * 1000
    }

    func testNormalizeNumber() {
        XCTAssertEqual(normalizeNumber("+1 (555) 123-4567"), "5551234567")
        XCTAssertEqual(normalizeNumber("15551234567"), "5551234567")
        XCTAssertEqual(normalizeNumber("555-1234"), "5551234")
        XCTAssertEqual(normalizeNumber(""), "")
    }

    func testWeekStartIsMondayUTC() {
        // 2026-01-01 is a Thursday; its week starts Monday 2025-12-29.
        XCTAssertEqual(weekStartMs(utcMs(2026, 1, 1, hour: 15)), utcMs(2025, 12, 29))
        // A Monday maps to itself.
        XCTAssertEqual(weekStartMs(utcMs(2025, 12, 29, hour: 3)), utcMs(2025, 12, 29))
    }

    func testWeekScoreWeights() {
        var w = WeekStats(weekStartMs: 0)
        w.texts = 3
        w.calls = 2
        w.callMinutes = 10
        w.missed = 1
        w.meets = 1
        XCTAssertEqual(w.score, 3 * 1 + 2 * 6 + 10 * 0.4 + 1 * 1 + 1 * 15, accuracy: 1e-9)
    }

    func testMeetsCountInBucketsAndTotals() {
        let monday = utcMs(2026, 1, 5)
        let now = monday + 2 * weekMs
        let events = [
            CommEvent(contactName: "Maya", number: "5551112222", kind: .text, direction: .outgoing, timestampMs: monday),
            CommEvent(contactName: "Maya", number: "5551112222", kind: .meet, direction: .met, timestampMs: monday + dayMs),
            CommEvent(contactName: "Maya", number: "5551112222", kind: .meet, direction: .met, timestampMs: monday + weekMs + dayMs),
        ]
        let (contacts, _) = analyzeAll(events, nowMs: now)
        let maya = contacts[0]
        XCTAssertEqual(maya.series[0].meets, 1)
        XCTAssertEqual(maya.series[1].meets, 1)
        XCTAssertEqual(maya.series[0].score, 1 + 15, accuracy: 1e-9)
        XCTAssertEqual(maya.totals.meets, 2)
        XCTAssertEqual(maya.daysSinceLastMeet, 6)
        // Meets are directionless: they never skew initiation balance.
        XCTAssertEqual(maya.outboundShare!, 1, accuracy: 1e-9)
    }

    func testDaysSinceLastMeetIsNilWithoutMeets() {
        let monday = utcMs(2026, 1, 5)
        let events = [
            CommEvent(contactName: "A", number: "5553334444", kind: .text, direction: .outgoing, timestampMs: monday),
            CommEvent(contactName: "A", number: "5553334444", kind: .text, direction: .incoming, timestampMs: monday + dayMs),
        ]
        let (contacts, _) = analyzeAll(events, nowMs: monday + weekMs)
        XCTAssertNil(contacts[0].daysSinceLastMeet)
    }

    func testWeeklySeriesIsContiguous() {
        let monday = utcMs(2026, 1, 5)
        let events = [
            CommEvent(kind: .text, direction: .outgoing, timestampMs: monday + dayMs),
            CommEvent(kind: .call, direction: .incoming, timestampMs: monday + 3 * weekMs + dayMs, durationSec: 600),
            CommEvent(kind: .call, direction: .missed, timestampMs: monday + 3 * weekMs + 2 * dayMs),
        ]
        let series = weeklySeries(events, nowMs: monday + 3 * weekMs + 4 * dayMs)
        XCTAssertEqual(series.count, 4)
        XCTAssertEqual(series.map(\.texts), [1, 0, 0, 0])
        XCTAssertEqual(series.map(\.calls), [0, 0, 0, 1])
        XCTAssertEqual(series.map(\.missed), [0, 0, 0, 1])
        XCTAssertEqual(series[3].callMinutes, 10)
        XCTAssertEqual(series[0].outgoing, 1)
        XCTAssertEqual(series[3].incoming, 1)
    }

    private func seriesOf(_ scores: [Double]) -> [WeekStats] {
        // Encode each score as texts so WeekStats.score reproduces it.
        scores.enumerated().map { i, score in
            var w = WeekStats(weekStartMs: Double(i) * weekMs)
            w.texts = Int(score)
            return w
        }
    }

    // Trailing 0 = the current in-progress week, which classification ignores.
    func testRisingTrend() {
        let t = classifyTrend(seriesOf(Array(repeating: 10, count: 8) + Array(repeating: 20, count: 4) + [0]))
        XCTAssertEqual(t.status, .rising)
        XCTAssertEqual(t.deltaPct!, 1, accuracy: 1e-9)
    }

    func testFadingTrend() {
        let t = classifyTrend(seriesOf(Array(repeating: 20, count: 8) + Array(repeating: 5, count: 4) + [0]))
        XCTAssertEqual(t.status, .fading)
        XCTAssertEqual(t.deltaPct!, -0.75, accuracy: 1e-9)
    }

    func testSteadyTrend() {
        let t = classifyTrend(seriesOf(Array(repeating: 10, count: 8) + Array(repeating: 11, count: 4) + [0]))
        XCTAssertEqual(t.status, .steady)
    }

    func testDormantAfterEightSilentWeeks() {
        let t = classifyTrend(seriesOf(Array(repeating: 15, count: 6) + Array(repeating: 0, count: 8) + [3]))
        XCTAssertEqual(t.status, .dormant)
    }

    func testShortHistoryIsSteadyWithNoDelta() {
        let t = classifyTrend(seriesOf([5, 6, 7]))
        XCTAssertEqual(t.status, .steady)
        XCTAssertNil(t.deltaPct)
    }

    func testInProgressWeekDoesNotDragTrendDown() {
        let t = classifyTrend(seriesOf(Array(repeating: 10, count: 12) + [1]))
        XCTAssertEqual(t.status, .steady)
        XCTAssertEqual(t.deltaPct!, 0, accuracy: 1e-9)
    }

    func testAnalyzeAllGroupsAndSkipsOneOffs() {
        let monday = utcMs(2026, 1, 5)
        let now = monday + 2 * weekMs
        let events = [
            // Same person, two formats of the same number
            CommEvent(contactName: "Mom", number: "+15551234567", kind: .text, direction: .outgoing, timestampMs: monday),
            CommEvent(contactName: "Mom", number: "5551234567", kind: .call, direction: .incoming, timestampMs: monday + dayMs, durationSec: 300),
            CommEvent(contactName: "", number: "5551234567", kind: .text, direction: .outgoing, timestampMs: monday + 2 * dayMs),
            // One-off number (spam / verification code): excluded
            CommEvent(contactName: "", number: "888555", kind: .text, direction: .incoming, timestampMs: monday),
        ]
        let (contacts, summary) = analyzeAll(events, nowMs: now)
        XCTAssertEqual(contacts.count, 1)
        let mom = contacts[0]
        XCTAssertEqual(mom.name, "Mom")
        XCTAssertEqual(mom.totals.texts, 2)
        XCTAssertEqual(mom.totals.calls, 1)
        XCTAssertEqual(mom.outboundShare!, 2.0 / 3.0, accuracy: 1e-9)
        XCTAssertEqual(mom.daysSinceLast, 12)
        XCTAssertEqual(summary.contacts, 1)
        XCTAssertEqual(summary.events, 3)
    }

    func testDemoDataClassifiesAsDesigned() {
        let now = utcMs(2026, 6, 17, hour: 12)
        let (contacts, _) = analyzeAll(DemoData.generate(nowMs: now), nowMs: now)
        XCTAssertEqual(contacts.count, 8)
        var byName: [String: TrendStatus] = [:]
        for c in contacts { byName[c.name] = c.trend.status }
        XCTAssertEqual(byName["Sam Okafor"], .dormant)
        XCTAssertEqual(byName["Jordan Reyes"], .fading)
        XCTAssertEqual(byName["Alex Chen"], .rising)
        XCTAssertEqual(byName["Casey Nguyen"], .rising)
        // Meets are deterministic (outside the LCG stream); values cross-checked
        // against the JS engine at this pinned date.
        let mom = contacts.first { $0.name == "Mom" }!
        XCTAssertEqual(mom.totals.meets, 13)
        XCTAssertEqual(mom.daysSinceLastMeet, 9)
    }
}
