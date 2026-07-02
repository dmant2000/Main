import SwiftUI
import Charts
import KindredCore

struct ContactDetailView: View {
    let contact: ContactAnalysis
    let rangeWeeks: Int

    @State private var showTable = false

    private var series: [WeekStats] {
        Array(contact.series.suffix(rangeWeeks))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                facts
                if showTable {
                    weeklyTable
                } else {
                    WeeklyColumnChart(
                        title: "Texts per week",
                        series: series,
                        value: { Double($0.texts) },
                        unit: "texts",
                        color: .seriesTexts
                    )
                    WeeklyColumnChart(
                        title: "Call minutes per week",
                        series: series,
                        value: \.callMinutes,
                        unit: "min",
                        color: .seriesCalls
                    )
                }
            }
            .padding()
        }
        .navigationTitle(contact.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button(showTable ? "Charts" : "Table") { showTable.toggle() }
            }
        }
    }

    private var header: some View {
        HStack(spacing: 10) {
            TrendBadge(status: contact.trend.status)
            if let delta = Formatters.delta(contact.trend.deltaPct) {
                Text(delta)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            if !contact.number.isEmpty {
                Text(formatNumber(contact.number))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var facts: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 100), spacing: 12)], spacing: 12) {
            Fact(value: "\(contact.totals.texts)", label: "texts")
            Fact(value: "\(contact.totals.calls)", label: "calls")
            Fact(value: "\(Int(contact.totals.callMinutes.rounded()))", label: "call minutes")
            Fact(
                value: contact.daysSinceLast == 0 ? "today" : "\(contact.daysSinceLast)d ago",
                label: "last contact"
            )
            if let share = contact.outboundShare {
                Fact(value: "\(Int((share * 100).rounded()))%", label: "started by you")
            }
        }
    }

    private var weeklyTable: some View {
        VStack(alignment: .leading, spacing: 0) {
            Grid(alignment: .trailing, horizontalSpacing: 12, verticalSpacing: 6) {
                GridRow {
                    Text("Week of").gridColumnAlignment(.leading)
                    Text("Texts")
                    Text("Calls")
                    Text("Min")
                    Text("Score")
                }
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
                Divider()
                ForEach(series, id: \.weekStartMs) { week in
                    GridRow {
                        Text(Formatters.weekLabel.string(from: week.weekStart))
                            .gridColumnAlignment(.leading)
                        Text("\(week.texts)")
                        Text("\(week.calls)")
                        Text("\(Int(week.callMinutes.rounded()))")
                        Text(String(format: "%.1f", week.score))
                    }
                    .font(.caption.monospacedDigit())
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct Fact: View {
    let value: String
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value)
                .font(.title3.weight(.semibold))
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct WeeklyColumnChart: View {
    let title: String
    let series: [WeekStats]
    let value: (WeekStats) -> Double
    let unit: String
    let color: Color

    @State private var selectedWeek: Date?

    private var selected: WeekStats? {
        guard let selectedWeek else { return nil }
        let ms = weekStartMs(selectedWeek.timeIntervalSince1970 * 1000)
        return series.first { $0.weekStartMs == ms }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)

            if let selected {
                Text("Week of \(Formatters.weekLabel.string(from: selected.weekStart)): ")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                + Text("\(Int(value(selected).rounded())) \(unit)")
                    .font(.caption.weight(.bold))
            } else {
                Text("Touch the chart for weekly values")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }

            Chart(series, id: \.weekStartMs) { week in
                BarMark(
                    x: .value("Week", week.weekStart, unit: .weekOfYear),
                    y: .value(unit, value(week))
                )
                .foregroundStyle(color)
                .cornerRadius(3)
                .opacity(selected == nil || selected?.weekStartMs == week.weekStartMs ? 1 : 0.55)
            }
            .chartXSelection(value: $selectedWeek)
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 5)) {
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.month(.abbreviated).day())
                }
            }
            .frame(height: 180)
        }
        .padding(14)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 12))
    }
}
