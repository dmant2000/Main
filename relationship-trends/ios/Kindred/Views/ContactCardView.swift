import SwiftUI
import Charts
import KindredCore

struct TrendBadge: View {
    let status: TrendStatus

    var body: some View {
        Label(status.label, systemImage: status.icon)
            .font(.caption2.weight(.semibold))
            .foregroundStyle(status.color)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .overlay(Capsule().strokeBorder(.quaternary))
    }
}

struct SparklineView: View {
    let scores: [Double]

    private struct Point: Identifiable {
        let id: Int
        let value: Double
    }

    private var points: [Point] {
        scores.enumerated().map { Point(id: $0.offset, value: $0.element) }
    }

    var body: some View {
        Chart(points) { point in
            AreaMark(x: .value("Week", point.id), y: .value("Score", point.value))
                .foregroundStyle(Color.seriesTexts.opacity(0.1))
            LineMark(x: .value("Week", point.id), y: .value("Score", point.value))
                .foregroundStyle(Color.seriesTexts)
                .lineStyle(StrokeStyle(lineWidth: 2, lineCap: .round, lineJoin: .round))
            if point.id == points.count - 1 {
                PointMark(x: .value("Week", point.id), y: .value("Score", point.value))
                    .foregroundStyle(Color.seriesTexts)
                    .symbolSize(50)
            }
        }
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .chartLegend(.hidden)
        .frame(height: 40)
        .accessibilityHidden(true)
    }
}

struct ContactCardView: View {
    let contact: ContactAnalysis
    let rangeWeeks: Int

    private var deltaText: (text: String, color: Color)? {
        if contact.trend.status == .dormant {
            return ("No contact in \(contact.daysSinceLast) days", .trendBad)
        }
        guard let text = Formatters.delta(contact.trend.deltaPct) else {
            return ("Building history…", .secondary)
        }
        let d = contact.trend.deltaPct ?? 0
        let color: Color = d >= Analysis.trendThreshold ? .trendGood
            : d <= -Analysis.trendThreshold ? .trendBad : .secondary
        return (text, color)
    }

    private var metaText: String {
        var parts = [contact.daysSinceLast == 0
            ? "Last contact today"
            : "Last contact \(contact.daysSinceLast)d ago"]
        if let seen = contact.daysSinceLastMeet {
            parts.append(seen == 0 ? "Seen today" : "Seen \(seen)d ago")
        }
        if let share = contact.outboundShare, contact.totals.events >= 10 {
            let pct = Int((share * 100).rounded())
            if pct >= 75 { parts.append("You reach out \(pct)% of the time") }
            else if pct <= 25 { parts.append("They reach out \(100 - pct)% of the time") }
        }
        return parts.joined(separator: " · ")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(contact.name)
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(1)
                Spacer(minLength: 4)
                TrendBadge(status: contact.trend.status)
            }
            SparklineView(scores: contact.series.suffix(rangeWeeks).map(\.score))
            if let delta = deltaText {
                Text(delta.text)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(delta.color)
            }
            Text(metaText)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 12))
    }
}
