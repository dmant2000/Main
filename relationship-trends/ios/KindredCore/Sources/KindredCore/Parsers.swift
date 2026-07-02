import Foundation

/// Parsers for communication exports — the Kindred CSV interchange format
/// (also produced by export-tools/export_comms.py) and the Android
/// "SMS Backup & Restore" calls.xml / sms.xml files.
public enum Parsers {
    public enum ParseError: LocalizedError {
        case missingColumns

        public var errorDescription: String? {
            switch self {
            case .missingColumns:
                return "CSV must have at least \"date\", \"kind\" and \"direction\" columns"
            }
        }
    }

    /// Sniff the format of a file's text content and parse accordingly.
    public static func parseAny(_ text: String) throws -> [CommEvent] {
        let head = String(text.prefix(2000))
        if head.contains("<calls") || head.contains("<call ") { return parseCallsXml(text) }
        if head.contains("<smses") || head.contains("<sms ") { return parseSmsXml(text) }
        return try parseCsv(text)
    }

    // MARK: - CSV

    /// Columns (case-insensitive): date (ISO 8601 or epoch ms), kind
    /// (text|call|meet), direction (in|out|missed; blank for meet), contact,
    /// number, duration_seconds. Extra columns are ignored.
    public static func parseCsv(_ text: String) throws -> [CommEvent] {
        let rows = splitCsv(text)
        guard rows.count >= 2 else { return [] }
        let header = rows[0].map { $0.trimmingCharacters(in: .whitespaces).lowercased() }
        guard
            let iDate = header.firstIndex(of: "date"),
            let iKind = header.firstIndex(of: "kind"),
            let iDir = header.firstIndex(of: "direction")
        else { throw ParseError.missingColumns }
        let iContact = header.firstIndex(of: "contact")
        let iNumber = header.firstIndex(of: "number")
        let iDur = header.firstIndex(of: "duration_seconds")

        var events: [CommEvent] = []
        for row in rows.dropFirst() {
            if row.count == 1 && row[0].trimmingCharacters(in: .whitespaces).isEmpty { continue }
            func field(_ i: Int?) -> String {
                guard let i, i < row.count else { return "" }
                return row[i].trimmingCharacters(in: .whitespaces)
            }
            guard let ts = parseDateMs(field(iDate)) else { continue }
            guard let kind = EventKind(rawValue: field(iKind).lowercased()) else { continue }
            let direction: Direction
            if kind == .meet {
                direction = .met // an in-person meet has no direction
            } else {
                guard let d = Direction(rawValue: field(iDir).lowercased()), d != .met else { continue }
                direction = d
            }
            events.append(CommEvent(
                contactName: cleanName(field(iContact)),
                number: field(iNumber),
                kind: kind,
                direction: direction,
                timestampMs: ts,
                durationSec: Double(field(iDur)) ?? 0
            ))
        }
        return events
    }

    static func parseDateMs(_ raw: String) -> Double? {
        guard !raw.isEmpty else { return nil }
        if raw.allSatisfy(\.isNumber) { return Double(raw) }
        let iso = ISO8601DateFormatter()
        if let d = iso.date(from: raw) { return d.timeIntervalSince1970 * 1000 }
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = iso.date(from: raw) { return d.timeIntervalSince1970 * 1000 }
        let plain = DateFormatter()
        plain.locale = Locale(identifier: "en_US_POSIX")
        plain.timeZone = TimeZone(identifier: "UTC")
        plain.dateFormat = "yyyy-MM-dd"
        if let d = plain.date(from: raw) { return d.timeIntervalSince1970 * 1000 }
        return nil
    }

    static func splitCsv(_ text: String) -> [[String]] {
        var rows: [[String]] = []
        var row: [String] = []
        var field = ""
        var inQuotes = false
        var i = text.startIndex
        while i < text.endIndex {
            let ch = text[i]
            if inQuotes {
                if ch == "\"" {
                    let next = text.index(after: i)
                    if next < text.endIndex && text[next] == "\"" {
                        field.append("\"")
                        i = next
                    } else {
                        inQuotes = false
                    }
                } else {
                    field.append(ch)
                }
            } else if ch == "\"" {
                inQuotes = true
            } else if ch == "," {
                row.append(field)
                field = ""
            } else if ch == "\n" || ch == "\r" {
                if ch == "\r" {
                    let next = text.index(after: i)
                    if next < text.endIndex && text[next] == "\n" { i = next }
                }
                row.append(field)
                field = ""
                rows.append(row)
                row = []
            } else {
                field.append(ch)
            }
        }
        if !field.isEmpty || !row.isEmpty {
            row.append(field)
            rows.append(row)
        }
        return rows
    }

    // MARK: - SMS Backup & Restore XML

    /// calls.xml — type: 1 incoming, 2 outgoing, 3 missed, 5 rejected.
    public static func parseCallsXml(_ xml: String) -> [CommEvent] {
        scanTags(xml, tagName: "call").compactMap { attrs in
            guard let ts = Double(attrs["date"] ?? ""), ts > 0 else { return nil }
            let direction: Direction
            switch attrs["type"] {
            case "2": direction = .outgoing
            case "1": direction = .incoming
            default: direction = .missed
            }
            return CommEvent(
                contactName: cleanName(attrs["contact_name"] ?? ""),
                number: attrs["number"] ?? "",
                kind: .call,
                direction: direction,
                timestampMs: ts,
                durationSec: direction == .missed ? 0 : Double(attrs["duration"] ?? "") ?? 0
            )
        }
    }

    /// sms.xml — type: 1 received, 2 sent (drafts/queued are skipped).
    public static func parseSmsXml(_ xml: String) -> [CommEvent] {
        scanTags(xml, tagName: "sms").compactMap { attrs in
            guard let ts = Double(attrs["date"] ?? ""), ts > 0 else { return nil }
            let direction: Direction
            switch attrs["type"] {
            case "1": direction = .incoming
            case "2": direction = .outgoing
            default: return nil
            }
            return CommEvent(
                contactName: cleanName(attrs["contact_name"] ?? ""),
                number: attrs["address"] ?? "",
                kind: .text,
                direction: direction,
                timestampMs: ts
            )
        }
    }

    /// Scan flat, machine-generated XML for a tag's attribute maps.
    static func scanTags(_ xml: String, tagName: String) -> [[String: String]] {
        guard
            let tagRe = try? NSRegularExpression(pattern: "<\(tagName)\\b([^>]*?)/?>"),
            let attrRe = try? NSRegularExpression(pattern: "([\\w:]+)\\s*=\\s*\"([^\"]*)\"")
        else { return [] }
        let ns = xml as NSString
        return tagRe.matches(in: xml, range: NSRange(location: 0, length: ns.length)).map { m in
            let body = ns.substring(with: m.range(at: 1))
            let bodyNs = body as NSString
            var attrs: [String: String] = [:]
            for a in attrRe.matches(in: body, range: NSRange(location: 0, length: bodyNs.length)) {
                let key = bodyNs.substring(with: a.range(at: 1))
                attrs[key] = decodeEntities(bodyNs.substring(with: a.range(at: 2)))
            }
            return attrs
        }
    }

    static func decodeEntities(_ str: String) -> String {
        guard str.contains("&") else { return str }
        var out = str
        for (entity, ch) in [("&lt;", "<"), ("&gt;", ">"), ("&quot;", "\""), ("&apos;", "'")] {
            out = out.replacingOccurrences(of: entity, with: ch)
        }
        // Numeric entities: &#65; and &#x42;
        if let re = try? NSRegularExpression(pattern: "&#(x?)([0-9a-fA-F]+);") {
            let ns = out as NSString
            var result = ""
            var last = 0
            for m in re.matches(in: out, range: NSRange(location: 0, length: ns.length)) {
                result += ns.substring(with: NSRange(location: last, length: m.range.location - last))
                let isHex = m.range(at: 1).length > 0
                let digits = ns.substring(with: m.range(at: 2))
                if let code = UInt32(digits, radix: isHex ? 16 : 10), let scalar = Unicode.Scalar(code) {
                    result.append(Character(scalar))
                } else {
                    result += ns.substring(with: m.range)
                }
                last = m.range.location + m.range.length
            }
            result += ns.substring(from: last)
            out = result
        }
        return out.replacingOccurrences(of: "&amp;", with: "&")
    }

    static func cleanName(_ name: String) -> String {
        let trimmed = name.trimmingCharacters(in: .whitespaces)
        if trimmed == "(Unknown)" || trimmed == "null" { return "" }
        return trimmed
    }
}
