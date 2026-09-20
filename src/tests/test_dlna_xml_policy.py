import codecs
import sys
import unittest
from xml.etree import ElementTree

sys.path.insert(0, "app/server")

from dlna.xml_policy import MAX_DLNA_XML_PARSE_BYTES, _UNSAFE_DECLARATION, safe_fromstring


class DlnaXmlPolicyTests(unittest.TestCase):
    # A five-deep, three-wide internal entity cascade: cheap to expand inside a
    # test (2430 characters) and enough to prove the parser really processed the
    # DTD rather than failing on something unrelated.
    ENTITY_LEVELS = 5
    ENTITY_WIDTH = 3

    @classmethod
    def _declaration_bomb(cls, declared_encoding):
        parts = ['<!ENTITY e0 "xxxxxxxxxx">']
        for level in range(1, cls.ENTITY_LEVELS + 1):
            parts.append('<!ENTITY e%d "%s">' % (level, ("&e%d;" % (level - 1)) * cls.ENTITY_WIDTH))
        return (
            '<?xml version="1.0" encoding="%s"?><!DOCTYPE bomb [%s]><root>&e%d;</root>'
            % (declared_encoding, "".join(parts), cls.ENTITY_LEVELS)
        )

    @classmethod
    def _clean_document(cls, declared_encoding):
        return '<?xml version="1.0" encoding="%s"?><root><name>Renderer</name></root>' % declared_encoding

    # expat picks the encoding from a BOM or from NUL padding, so a peer may send
    # any one of these and the parser will decode it.
    VARIANTS = (
        ("us-ascii", "US-ASCII", lambda text: text.encode("ascii")),
        ("utf-8", "UTF-8", lambda text: text.encode("utf-8")),
        ("utf-8 with BOM", "UTF-8", lambda text: codecs.BOM_UTF8 + text.encode("utf-8")),
        ("utf-16 with LE BOM", "UTF-16", lambda text: text.encode("utf-16")),
        ("utf-16 with BE BOM", "UTF-16", lambda text: codecs.BOM_UTF16_BE + text.encode("utf-16-be")),
        ("utf-16le without BOM", "UTF-16LE", lambda text: text.encode("utf-16-le")),
        ("utf-16be without BOM", "UTF-16BE", lambda text: text.encode("utf-16-be")),
    )

    def test_the_bomb_fixture_really_expands_when_it_reaches_the_parser(self):
        # The rejection tests are only worth something if this payload is one the
        # parser would actually have expanded, not one that fails for an
        # unrelated reason.  ElementTree is called directly here on purpose.
        document = self._declaration_bomb("UTF-16")
        root = ElementTree.fromstring(document.encode("utf-16"))
        expanded = "".join(root.itertext())
        self.assertEqual(len(expanded), self.ENTITY_WIDTH ** self.ENTITY_LEVELS * 10)
        self.assertLess(len(document), len(expanded))

    def test_accepts_normal_xml(self):
        root = safe_fromstring(b"<root><name>Renderer</name></root>")
        self.assertEqual(root.findtext("name"), "Renderer")

    def test_rejects_dtd_and_entity_declarations(self):
        for payload in (
            b'<!DOCTYPE root [<!ENTITY x "expanded">]><root>&x;</root>',
            b'<!ENTITY x "expanded"><root/>',
        ):
            with self.assertRaises(ValueError):
                safe_fromstring(payload)

    def test_rejects_declarations_in_every_encoding_expat_accepts(self):
        for label, declared, build in self.VARIANTS:
            with self.subTest(encoding=label):
                payload = build(self._declaration_bomb(declared))
                # A ParseError would mean the guard never fired and the parser
                # only failed by accident, so the message is pinned as well.
                with self.assertRaisesRegex(ValueError, "declarations are not allowed"):
                    safe_fromstring(payload)

    def test_nul_padding_hides_a_declaration_from_a_raw_byte_scan(self):
        for label, declared, build in self.VARIANTS:
            payload = build(self._declaration_bomb(declared))
            if b"\x00" not in payload:
                continue
            with self.subTest(encoding=label):
                self.assertIsNone(
                    _UNSAFE_DECLARATION.search(payload),
                    "a NUL-padded declaration must miss the raw scan; that is the bypass",
                )
                with self.assertRaises(ValueError):
                    safe_fromstring(payload)

    def test_the_same_encoding_without_a_declaration_still_parses(self):
        for label, declared, build in self.VARIANTS:
            with self.subTest(encoding=label):
                root = safe_fromstring(build(self._clean_document(declared)))
                self.assertEqual(root.findtext("name"), "Renderer")

    def test_lone_nul_cannot_split_a_declaration(self):
        payload = b'<!E\x00NTITY x "expanded"><root/>'
        self.assertIsNone(_UNSAFE_DECLARATION.search(payload))
        with self.assertRaisesRegex(ValueError, "declarations are not allowed"):
            safe_fromstring(payload)

    def test_escaped_markup_in_a_utf16_body_is_not_a_declaration(self):
        # A real SOAP body can carry escaped DIDL metadata.  Folding NUL bytes
        # must not turn that text into a rejected declaration.
        body = (
            '<?xml version="1.0" encoding="UTF-16"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><s:Body>'
            '<u:SetAVTransportURI>&lt;!ENTITY x SYSTEM "file:///etc/passwd"&gt;'
            "</u:SetAVTransportURI></s:Body></s:Envelope>"
        )
        root = safe_fromstring(body.encode("utf-16"))
        value = root.findtext(".//{urn:schemas-upnp-org:service:AVTransport:1}SetAVTransportURI")
        self.assertIn('!ENTITY x SYSTEM "file:///etc/passwd"', value or "")

    def test_rejects_oversized_or_untrusted_input(self):
        with self.assertRaises(ValueError):
            safe_fromstring(b"<root/>", maximum=True)
        with self.assertRaises(ValueError):
            safe_fromstring(b"<root/>", maximum=MAX_DLNA_XML_PARSE_BYTES + 1)
        with self.assertRaises(ValueError):
            safe_fromstring(object())


if __name__ == "__main__":
    unittest.main()
