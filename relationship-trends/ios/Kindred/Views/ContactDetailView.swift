import SwiftUI
import Charts
import KindredCore

struct ContactDetailView: View {
    let contactID: String
    let rangeWeeks: Int

    @EnvironmentObject private var store: DataStore

    var body: some View {
        if let contact = store.contacts.first(where: { $0.id == contactID }) {
            DetailContent(contact: contact, rangeWeeks: rangeWeeks)
        } else {
            ContentUnavailableView("No data for this contact", systemImage: "person.slash")
        }
    }
}

private struct DetailContent: View {
    let contact: ContactAnalysis
    let rangeWeeks: Int

    @EnvironmentObject private var store: DataStore
    @State private var showTable = false
    @State private var showLogSheet = false
    @State private var showCalendarSheet = false
    @State private var candidates: [CalendarCandidate] = []
    @State private var scanning = false
    @State private var scanMessage: String?

    private var series: [WeekStats] {
        Array(contact.series.suffix(rangeWeeks))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                facts
                inPersonSection
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
        .sheet(isPresented: $showLogSheet) {
            LogMeetSheet(contact: contact)
        }
        .sheet(isPresented: $showCalendarSheet) {
            CalendarCandidatesSheet(contact: contact, candidates: candidates)
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
            Fact(value: "\(contact.totals.meets)", label: "hangouts")
            Fact(
                value: contact.daysSinceLast == 0 ? "today" : "\(contact.daysSinceLast)d ago",
                label: "last contact"
            )
            if let share = contact.outboundShare {
                Fact(value: "\(Int((share * 100).rounded()))%", label: "started by you")
            }
        }
    }

    // MARK: - In person

    private var lastSeenText: String {
        switch contact.daysSinceLastMeet {
        case nil: return "You have no in-person hangouts logged with \(contact.name)."
        case .some(0): return "You saw \(contact.name) in person today."
        case .some(let days): return "You last saw \(contact.name) in person \(days) day\(days == 1 ? "" : "s") ago."
        }
    }

    private var inPersonSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("In person")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(lastSeenText)
                .font(.callout)
            HStack(spacing: 10) {
                Button {
                    Task { await scanCalendar() }
                } label: {
                    if scanning {
                        ProgressView()
                    } else {
                        Label("Check Calendar", systemImage: "calendar.badge.checkmark")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(scanning)

                Button("Log a hangout…", systemImage: "figure.2") {
                    showLogSheet = true
                }
                .buttonStyle(.bordered)
            }
            if let scanMessage {
                Text(scanMessage)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 12))
    }

    private func scanCalendar() async {
        scanning = true
        scanMessage = nil
        defer { scanning = false }
        do {
            let found = try await CalendarScanner.findCandidates(matching: contact.name)
            if found.isEmpty {
                scanMessage = "No calendar events mentioning “\(contact.name)” in the last 6 months."
            } else {
                candidates = found
                showCalendarSheet = true
            }
        } catch {
            scanMessage = error.localizedDescription
        }
    }

    private var weeklyTable: some View {
        VStack(alignment: .leading, spacing: 0) {
            Grid(alignment: .trailing, horizontalSpacing: 12, verticalSpacing: 6) {
                GridRow {
                    Text("Week of").gridColumnAlignment(.leading)
                    Text("Texts")
                    Text("Calls")
                    Text("Met")
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
                        Text("\(week.meets)")
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

// MARK: - Sheets

private struct LogMeetSheet: View {
    let contact: ContactAnalysis

    @EnvironmentObject private var store: DataStore
    @Environment(\.dismiss) private var dismiss
    @State private var date = Date()

    var body: some View {
        NavigationStack {
            Form {
                DatePicker(
                    "When did you meet?",
                    selection: $date,
                    in: ...Date(),
                    displayedComponents: .date
                )
            }
            .navigationTitle("Log a hangout")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        store.logMeets(with: contact, on: [date])
                        dismiss()
                    }
                }
            }
        }
        .presentationDetents([.medium])
    }
}

private struct CalendarCandidatesSheet: View {
    let contact: ContactAnalysis
    let candidates: [CalendarCandidate]

    @EnvironmentObject private var store: DataStore
    @Environment(\.dismiss) private var dismiss
    @State private var selected: Set<String> = []

    var body: some View {
        NavigationStack {
            List(candidates, selection: $selected) { candidate in
                VStack(alignment: .leading, spacing: 2) {
                    Text(candidate.title)
                        .font(.subheadline)
                    Text(candidate.date.formatted(date: .abbreviated, time: .shortened))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .environment(\.editMode, .constant(.active))
            .navigationTitle("Found \(candidates.count) event\(candidates.count == 1 ? "" : "s")")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add \(selected.count)") {
                        let dates = candidates
                            .filter { selected.contains($0.id) }
                            .map(\.date)
                        store.logMeets(with: contact, on: dates)
                        dismiss()
                    }
                    .disabled(selected.isEmpty)
                }
            }
        }
    }
}
