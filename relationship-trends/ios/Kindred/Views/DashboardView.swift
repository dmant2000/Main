import SwiftUI
import UniformTypeIdentifiers
import KindredCore

struct DashboardView: View {
    @EnvironmentObject private var store: DataStore
    @State private var showImporter = false

    var body: some View {
        NavigationStack {
            Group {
                if store.hasData {
                    dashboard
                } else {
                    OnboardingView(showImporter: $showImporter)
                }
            }
            .navigationTitle("Kindred")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button("Import files…", systemImage: "square.and.arrow.down") {
                            showImporter = true
                        }
                        Button("Load demo data", systemImage: "sparkles") {
                            store.loadDemo()
                        }
                        Button("Use contact names", systemImage: "person.crop.circle") {
                            Task { await store.resolveNamesFromContacts() }
                        }
                        Divider()
                        Button("Clear data", systemImage: "trash", role: .destructive) {
                            store.clear()
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .fileImporter(
                isPresented: $showImporter,
                allowedContentTypes: [.commaSeparatedText, .xml, .plainText],
                allowsMultipleSelection: true
            ) { result in
                if case .success(let urls) = result {
                    store.importFiles(urls)
                }
            }
            .alert("Import issue", isPresented: Binding(
                get: { store.lastError != nil },
                set: { if !$0 { store.lastError = nil } }
            )) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(store.lastError ?? "")
            }
        }
    }

    private var dashboard: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Picker("Range", selection: $store.rangeWeeks) {
                    Text("3 mo").tag(13)
                    Text("6 mo").tag(26)
                    Text("12 mo").tag(52)
                    Text("All").tag(Int.max)
                }
                .pickerStyle(.segmented)

                tiles

                Text("People")
                    .font(.headline)

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 165), spacing: 12)], spacing: 12) {
                    ForEach(store.contacts) { contact in
                        NavigationLink(value: contact.id) {
                            ContactCardView(contact: contact, rangeWeeks: store.rangeWeeks)
                        }
                        .buttonStyle(.plain)
                    }
                }

                if !store.sourceLabel.isEmpty {
                    Text(store.sourceLabel)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding()
        }
        .navigationDestination(for: String.self) { contactID in
            if let contact = store.contacts.first(where: { $0.id == contactID }) {
                ContactDetailView(contact: contact, rangeWeeks: store.rangeWeeks)
            }
        }
    }

    private var tiles: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            StatTile(label: "People tracked", value: "\(store.summary.contacts)")
            StatTile(label: "Interactions", value: "\(store.summary.events)")
            StatTile(
                label: "Trending up",
                value: "\(store.summary.rising)",
                tone: store.summary.rising > 0 ? .trendGood : nil
            )
            StatTile(
                label: "Trending down",
                value: "\(store.summary.fading)",
                tone: store.summary.fading > 0 ? .trendBad : nil
            )
        }
    }
}

struct StatTile: View {
    let label: String
    let value: String
    var tone: Color?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title.weight(.semibold))
                .foregroundStyle(tone ?? .primary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 12))
    }
}

struct OnboardingView: View {
    @EnvironmentObject private var store: DataStore
    @Binding var showImporter: Bool

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Label("Everything stays on this device. Nothing is uploaded anywhere.",
                      systemImage: "lock.fill")
                    .font(.footnote)
                    .foregroundStyle(.secondary)

                Text("Are your relationships trending up or down?")
                    .font(.title2.weight(.semibold))

                Text("""
                iOS doesn't let any app read your messages or call log directly, \
                so Kindred works from an export:

                1. On a Mac your iPhone syncs to, run the exporter script from the \
                Kindred repo (export-tools/export_comms.py mac). No Mac? Make a local \
                unencrypted iPhone backup with Finder or iTunes and run the backup \
                mode instead.
                2. AirDrop or save the resulting kindred.csv to this phone.
                3. Import it below — then tap “Use contact names” in the menu to \
                turn phone numbers into names from your address book.

                Android exports from SMS Backup & Restore (calls.xml / sms.xml) \
                work too.
                """)
                .font(.callout)
                .foregroundStyle(.secondary)

                HStack {
                    Button("Import files…") { showImporter = true }
                        .buttonStyle(.borderedProminent)
                    Button("Load demo data") { store.loadDemo() }
                        .buttonStyle(.bordered)
                }
            }
            .padding()
        }
    }
}
