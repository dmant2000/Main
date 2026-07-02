import Foundation

/// Deterministic demo dataset: eight relationships with distinct trajectories
/// over the 26 weeks leading up to `now`. Seeded LCG, so the demo looks the
/// same on every load (modulo the current date). Mirrors the web app's demo.
public enum DemoData {
    private struct Profile {
        let name: String
        let number: String
        let seed: UInt32
        let texts: (Int) -> Double
        let calls: (Int) -> Double
        let callMin: Double
        let outShare: Double
        /// Weeks with an in-person hangout. Meets are generated arithmetically
        /// (no random draws) so they never perturb the seeded stream — this
        /// must stay bit-identical with the web app's demo.js.
        let meetWeek: (Int) -> Bool
    }

    private static func ramp(_ from: Double, _ to: Double, _ week: Int) -> Double {
        from + (to - from) * Double(week) / 25
    }

    private static let profiles: [Profile] = [
        Profile(name: "Mom", number: "+15551000001", seed: 11,
                texts: { _ in 6 }, calls: { _ in 1 }, callMin: 22, outShare: 0.45,
                meetWeek: { w in w % 2 == 0 }),
        Profile(name: "Dad", number: "+15551000002", seed: 22,
                texts: { _ in 2 }, calls: { w in w % 2 == 0 ? 1 : 0.2 }, callMin: 15, outShare: 0.5,
                meetWeek: { w in w % 4 == 1 }),
        // Accelerating ramp so the last month clearly outpaces the baseline.
        Profile(name: "Alex Chen", number: "+15551000003", seed: 33,
                texts: { w in 2 + 18 * pow(Double(w) / 25, 2) },
                calls: { w in 1.6 * pow(Double(w) / 25, 2) }, callMin: 12, outShare: 0.5,
                meetWeek: { w in w >= 18 && w % 2 == 1 }),
        Profile(name: "Jordan Reyes", number: "+15551000004", seed: 44,
                texts: { w in ramp(20, 2, w) }, calls: { w in ramp(1.5, 0.1, w) }, callMin: 18, outShare: 0.55,
                meetWeek: { w in w < 10 && w % 2 == 0 }),
        Profile(name: "Riley Park", number: "+15551000005", seed: 55,
                texts: { _ in 8 }, calls: { _ in 0.1 }, callMin: 6, outShare: 0.5,
                meetWeek: { _ in false }),
        Profile(name: "Sam Okafor", number: "+15551000006", seed: 66,
                texts: { w in w < 14 ? 7 : 0 }, calls: { w in w < 14 ? 0.6 : 0 }, callMin: 25, outShare: 0.5,
                meetWeek: { w in w < 14 && w % 4 == 2 }),
        // One-sided: steady texting, but the user starts nearly every exchange.
        Profile(name: "Taylor Brooks", number: "+15551000007", seed: 77,
                texts: { _ in 5 }, calls: { _ in 0 }, callMin: 9, outShare: 0.88,
                meetWeek: { _ in false }),
        // New friend: quiet start ~3 months ago, ramping hard in recent weeks.
        Profile(name: "Casey Nguyen", number: "+15551000008", seed: 88,
                texts: { w in w < 14 ? 0 : 1 + 15 * Double(w - 14) / 11 },
                calls: { w in w < 14 ? 0 : 0.8 * Double(w - 14) / 11 }, callMin: 10, outShare: 0.5,
                meetWeek: { w in w >= 22 && w % 2 == 0 }),
    ]

    private struct LCG {
        var state: UInt32
        mutating func next() -> Double {
            state = state &* 1664525 &+ 1013904223
            return Double(state) / Double(UInt64(1) << 32)
        }
    }

    public static func generate(nowMs: Double = Date().timeIntervalSince1970 * 1000) -> [CommEvent] {
        let weekMs = Analysis.weekMs
        let dayMs = Analysis.dayMs
        var events: [CommEvent] = []
        let start = nowMs - 26 * weekMs
        for p in profiles {
            var rand = LCG(state: p.seed)
            for w in 0..<26 {
                let weekBase = start + Double(w) * weekMs
                let jitter = 0.75 + rand.next() * 0.5
                let nTexts = max(0, Int((p.texts(w) * jitter).rounded()))
                for _ in 0..<nTexts {
                    let ts = weekBase + (rand.next() * (weekMs - dayMs)).rounded(.down)
                    guard ts <= nowMs else { continue }
                    events.append(CommEvent(
                        contactName: p.name, number: p.number, kind: .text,
                        direction: rand.next() < p.outShare ? .outgoing : .incoming,
                        timestampMs: ts
                    ))
                }
                let expectedCalls = p.calls(w)
                let fraction = expectedCalls.truncatingRemainder(dividingBy: 1)
                let nCalls = rand.next() < fraction
                    ? Int(expectedCalls.rounded(.up))
                    : Int(expectedCalls.rounded(.down))
                for _ in 0..<nCalls {
                    let ts = weekBase + (rand.next() * (weekMs - dayMs)).rounded(.down)
                    guard ts <= nowMs else { continue }
                    let missed = rand.next() < 0.12
                    let direction: Direction = missed
                        ? .missed
                        : rand.next() < p.outShare ? .outgoing : .incoming
                    events.append(CommEvent(
                        contactName: p.name, number: p.number, kind: .call,
                        direction: direction,
                        timestampMs: ts,
                        durationSec: missed ? 0 : (p.callMin * 60 * (0.7 + rand.next() * 0.6)).rounded()
                    ))
                }
                if p.meetWeek(w) {
                    // Friday evening, fixed offset: deterministic and outside the LCG stream.
                    let ts = weekBase + 4 * dayMs + 19 * 60 * 60 * 1000
                    if ts <= nowMs {
                        events.append(CommEvent(
                            contactName: p.name, number: p.number, kind: .meet,
                            direction: .met, timestampMs: ts
                        ))
                    }
                }
            }
        }
        events.sort { $0.timestampMs < $1.timestampMs }
        return events
    }
}
