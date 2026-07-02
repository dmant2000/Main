import XCTest
@testable import KindredCore

final class ParsersTests: XCTestCase {
    private let callsXml = """
    <?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <calls count="4">
      <call number="+15551234567" duration="120" date="1735689600000" type="1" contact_name="Mom" />
      <call number="+15551234567" duration="300" date="1735776000000" type="2" contact_name="Mom" />
      <call number="5559876543" duration="0" date="1735862400000" type="3" contact_name="Jordan &amp; Co" />
      <call number="5550001111" duration="60" date="0" type="1" contact_name="Bad Date" />
    </calls>
    """

    private let smsXml = """
    <?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <smses count="4">
      <sms address="+15551234567" date="1735689700000" type="1" body="hi" contact_name="Mom" />
      <sms address="+15551234567" date="1735689800000" type="2" body="hello" contact_name="Mom" />
      <sms address="5559876543" date="1735689900000" type="3" body="draft" contact_name="Jordan" />
      <sms address="5559876543" date="1735690000000" type="1" body="yo" contact_name="(Unknown)" />
    </smses>
    """

    func testParseCallsXml() {
        let events = Parsers.parseCallsXml(callsXml)
        XCTAssertEqual(events.count, 3)
        XCTAssertEqual(events[0].contactName, "Mom")
        XCTAssertEqual(events[0].direction, .incoming)
        XCTAssertEqual(events[0].timestampMs, 1735689600000)
        XCTAssertEqual(events[0].durationSec, 120)
        XCTAssertEqual(events[1].direction, .outgoing)
        XCTAssertEqual(events[2].direction, .missed)
        XCTAssertEqual(events[2].contactName, "Jordan & Co")
    }

    func testParseSmsXml() {
        let events = Parsers.parseSmsXml(smsXml)
        XCTAssertEqual(events.count, 3)
        XCTAssertEqual(events[0].direction, .incoming)
        XCTAssertEqual(events[1].direction, .outgoing)
        XCTAssertEqual(events[2].contactName, "")
        XCTAssertTrue(events.allSatisfy { $0.kind == .text })
    }

    func testParseCsv() throws {
        let csv = """
        date,kind,direction,contact,number,duration_seconds
        2026-01-01T10:00:00Z,text,in,"Reyes, Jordan",5559876543,
        1735776000000,call,out,Mom,+15551234567,300
        not-a-date,call,in,Bad,555,10
        2026-01-02T10:00:00Z,email,in,Skip,555,

        """
        let events = try Parsers.parseCsv(csv)
        XCTAssertEqual(events.count, 2)
        XCTAssertEqual(events[0].contactName, "Reyes, Jordan")
        XCTAssertEqual(events[1].durationSec, 300)
    }

    func testParseCsvThrowsOnMissingColumns() {
        XCTAssertThrowsError(try Parsers.parseCsv("a,b\n1,2"))
    }

    func testParseAnySniffsFormat() throws {
        XCTAssertEqual(try Parsers.parseAny(callsXml).first?.kind, .call)
        XCTAssertEqual(try Parsers.parseAny(smsXml).first?.kind, .text)
        XCTAssertEqual(try Parsers.parseAny("date,kind,direction\n2026-01-01,text,in").first?.kind, .text)
    }

    func testDecodeEntities() {
        XCTAssertEqual(Parsers.decodeEntities("A &amp; B &lt;3 &#65; &#x42;"), "A & B <3 A B")
    }
}
