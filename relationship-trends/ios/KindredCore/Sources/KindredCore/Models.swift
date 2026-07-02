import Foundation

public enum EventKind: String, Codable, Sendable {
    case text
    case call
}

public enum Direction: String, Codable, Sendable {
    case incoming = "in"
    case outgoing = "out"
    case missed
}

/// One text message or phone call. Timestamps are epoch milliseconds so the
/// analysis math mirrors the web app exactly; convert to Date only at the UI.
public struct CommEvent: Codable, Equatable, Hashable, Sendable {
    public var contactName: String
    public var number: String
    public var kind: EventKind
    public var direction: Direction
    public var timestampMs: Double
    public var durationSec: Double

    public init(
        contactName: String = "",
        number: String = "",
        kind: EventKind,
        direction: Direction,
        timestampMs: Double,
        durationSec: Double = 0
    ) {
        self.contactName = contactName
        self.number = number
        self.kind = kind
        self.direction = direction
        self.timestampMs = timestampMs
        self.durationSec = durationSec
    }

    public var date: Date { Date(timeIntervalSince1970: timestampMs / 1000) }
}
