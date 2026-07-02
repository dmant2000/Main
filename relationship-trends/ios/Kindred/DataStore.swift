import Foundation
import Contacts
import KindredCore

/// Owns the imported events, persists them locally as JSON, and exposes the
/// analysis. All data stays on-device.
@MainActor
final class DataStore: ObservableObject {
    @Published private(set) var events: [CommEvent] = []
    @Published private(set) var contacts: [ContactAnalysis] = []
    @Published private(set) var summary = Summary()
    @Published var rangeWeeks = 26
    @Published private(set) var sourceLabel = ""
    @Published var lastError: String?

    private var fileURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("kindred-events.json")
    }

    init() {
        loadFromDisk()
    }

    var hasData: Bool { !contacts.isEmpty }

    // MARK: - Loading data

    func loadDemo() {
        events = DemoData.generate()
        sourceLabel = "Demo data · \(events.count) events"
        persistAndReanalyze()
    }

    func importFiles(_ urls: [URL]) {
        var imported: [CommEvent] = []
        var errors: [String] = []
        for url in urls {
            let scoped = url.startAccessingSecurityScopedResource()
            defer { if scoped { url.stopAccessingSecurityScopedResource() } }
            do {
                let text = try String(contentsOf: url, encoding: .utf8)
                let parsed = try Parsers.parseAny(text)
                if parsed.isEmpty { errors.append("\(url.lastPathComponent): no events recognized") }
                imported.append(contentsOf: parsed)
            } catch {
                errors.append("\(url.lastPathComponent): \(error.localizedDescription)")
            }
        }
        lastError = errors.isEmpty ? nil : errors.joined(separator: "\n")
        guard !imported.isEmpty else { return }
        // Merge with whatever is already loaded, dropping exact duplicates so
        // re-importing an overlapping export is safe.
        let merged = Set(events).union(imported)
        events = merged.sorted { $0.timestampMs < $1.timestampMs }
        sourceLabel = "\(events.count) events imported"
        persistAndReanalyze()
    }

    func clear() {
        events = []
        sourceLabel = ""
        try? FileManager.default.removeItem(at: fileURL)
        reanalyze()
    }

    // MARK: - In-person meets

    /// Log in-person hangouts with a contact. Days that already have a meet
    /// logged for this contact are skipped, so confirming the same calendar
    /// event twice is harmless. Returns how many were actually added.
    @discardableResult
    func logMeets(with contact: ContactAnalysis, on dates: [Date]) -> Int {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "UTC") ?? .current
        var existingDays = Set(
            events
                .filter { $0.kind == .meet && contactKey(for: $0) == contact.id }
                .map { cal.startOfDay(for: $0.date) }
        )
        var added = 0
        for date in dates {
            let day = cal.startOfDay(for: date)
            guard !existingDays.contains(day) else { continue }
            existingDays.insert(day)
            events.append(CommEvent(
                contactName: contact.name,
                number: contact.number,
                kind: .meet,
                direction: .met,
                timestampMs: date.timeIntervalSince1970 * 1000
            ))
            added += 1
        }
        guard added > 0 else { return 0 }
        events.sort { $0.timestampMs < $1.timestampMs }
        persistAndReanalyze()
        return added
    }

    // MARK: - Contact name resolution (the iOS-native advantage)

    /// Exports carry numbers, not names. With permission, map numbers to the
    /// user's address book names — entirely on-device.
    func resolveNamesFromContacts() async {
        let cnStore = CNContactStore()
        do {
            let granted = try await cnStore.requestAccess(for: .contacts)
            guard granted else {
                lastError = "Contacts access was declined — names stay as phone numbers."
                return
            }
        } catch {
            lastError = error.localizedDescription
            return
        }

        let keys = [
            CNContactGivenNameKey, CNContactFamilyNameKey, CNContactPhoneNumbersKey,
        ] as [CNKeyDescriptor]
        let request = CNContactFetchRequest(keysToFetch: keys)
        var nameByNumber: [String: String] = [:]
        do {
            try cnStore.enumerateContacts(with: request) { contact, _ in
                let name = "\(contact.givenName) \(contact.familyName)"
                    .trimmingCharacters(in: .whitespaces)
                guard !name.isEmpty else { return }
                for phone in contact.phoneNumbers {
                    let key = normalizeNumber(phone.value.stringValue)
                    if !key.isEmpty { nameByNumber[key] = name }
                }
            }
        } catch {
            lastError = error.localizedDescription
            return
        }

        events = events.map { event in
            var e = event
            if e.contactName.isEmpty, let name = nameByNumber[normalizeNumber(e.number)] {
                e.contactName = name
            }
            return e
        }
        persistAndReanalyze()
    }

    // MARK: - Persistence & analysis

    private func loadFromDisk() {
        if let data = try? Data(contentsOf: fileURL),
           let saved = try? JSONDecoder().decode([CommEvent].self, from: data) {
            events = saved
            sourceLabel = "\(events.count) events"
        }
        reanalyze()
    }

    private func persistAndReanalyze() {
        if let data = try? JSONEncoder().encode(events) {
            try? data.write(to: fileURL, options: .atomic)
        }
        reanalyze()
    }

    private func reanalyze() {
        let result = analyzeAll(events, nowMs: Date().timeIntervalSince1970 * 1000)
        contacts = result.contacts
        summary = result.summary
    }
}
