import Foundation
import EventKit
import KindredCore

/// A calendar event that looks like it might have been an in-person meetup
/// with a given contact.
struct CalendarCandidate: Identifiable {
    let id: String
    let title: String
    let date: Date
}

enum CalendarScanError: LocalizedError {
    case accessDenied

    var errorDescription: String? {
        switch self {
        case .accessDenied:
            return "Calendar access was declined — you can still log hangouts manually."
        }
    }
}

/// Scans the user's calendar (on-device, read-only) for past events that
/// mention a contact, so they can be confirmed as in-person hangouts. This is
/// the closest iOS gets to "was I with this person?" — there is no presence
/// API, but shared plans usually live in the calendar.
enum CalendarScanner {
    static func findCandidates(
        matching contactName: String,
        monthsBack: Int = 6
    ) async throws -> [CalendarCandidate] {
        let store = EKEventStore()
        guard try await store.requestFullAccessToEvents() else {
            throw CalendarScanError.accessDenied
        }

        let end = Date()
        guard let start = Calendar.current.date(byAdding: .month, value: -monthsBack, to: end) else {
            return []
        }
        let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
        let needle = contactName.trimmingCharacters(in: .whitespaces).lowercased()
        guard !needle.isEmpty else { return [] }

        return store.events(matching: predicate)
            .filter { event in
                if event.isAllDay && event.title == nil { return false }
                if let title = event.title?.lowercased(), title.contains(needle) { return true }
                let attendees = event.attendees ?? []
                return attendees.contains { $0.name?.lowercased().contains(needle) == true }
            }
            .map { event in
                CalendarCandidate(
                    id: event.eventIdentifier ?? UUID().uuidString,
                    title: event.title ?? "Untitled event",
                    date: event.startDate
                )
            }
            .sorted { $0.date > $1.date }
    }
}
