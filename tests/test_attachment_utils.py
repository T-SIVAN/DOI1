import unittest

from attachment_utils import build_attachment_context, extract_attachment_text


class UploadedStub:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


class AttachmentUtilsTests(unittest.TestCase):
    def test_plain_text_and_json_are_extracted(self):
        self.assertEqual(extract_attachment_text("notes.md", "研究假设".encode("utf-8")), "研究假设")
        json_text = extract_attachment_text("data.json", b'{"effect": 1.2}')
        self.assertIn('"effect": 1.2', json_text)

    def test_context_keeps_file_names_and_reports_empty_files(self):
        context, warnings = build_attachment_context(
            [UploadedStub("notes.txt", "实验记录".encode("utf-8")), UploadedStub("empty.txt", b"")]
        )
        self.assertIn("附件：notes.txt", context)
        self.assertIn("实验记录", context)
        self.assertTrue(any("empty.txt" in warning for warning in warnings))
