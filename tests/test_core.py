"""Tests for newline_normalizer_rewriter.core.

Every test operates on bytes so results are identical on POSIX and Windows.
File-based tests use tempfile directories created per-test so there is no
shared state between tests.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from newline_normalizer_rewriter.core import (
    normalize_bytes,
    normalize_file,
    normalize_files,
)


class TestNormalizeBytes(unittest.TestCase):

    def test_no_newlines_unchanged(self):
        self.assertEqual(normalize_bytes(b"hello world"), b"hello world")

    def test_lf_to_lf_noop(self):
        self.assertEqual(normalize_bytes(b"a\nb\n", b"\n"), b"a\nb\n")

    def test_crlf_to_lf(self):
        self.assertEqual(normalize_bytes(b"a\r\nb\r\n", b"\n"), b"a\nb\n")

    def test_cr_to_lf(self):
        self.assertEqual(normalize_bytes(b"a\rb\r", b"\n"), b"a\nb\n")

    def test_lf_to_crlf(self):
        self.assertEqual(normalize_bytes(b"a\nb\n", b"\r\n"), b"a\r\nb\r\n")

    def test_cr_to_crlf(self):
        self.assertEqual(normalize_bytes(b"a\rb\r", b"\r\n"), b"a\r\nb\r\n")

    def test_crlf_to_cr(self):
        self.assertEqual(normalize_bytes(b"a\r\nb\r\n", b"\r"), b"a\rb\r")

    def test_mixed_all_to_lf(self):
        src = b"line1\r\nline2\rline3\nline4\r\n"
        self.assertEqual(normalize_bytes(src, b"\n"), b"line1\nline2\nline3\nline4\n")

    def test_mixed_all_to_crlf(self):
        src = b"a\rb\nc\r\n"
        self.assertEqual(normalize_bytes(src, b"\r\n"), b"a\r\nb\r\nc\r\n")

    def test_default_target_is_lf(self):
        self.assertEqual(normalize_bytes(b"a\r\nb\r"), b"a\nb\n")

    def test_trailing_lone_cr_before_lf(self):
        # A lone CR followed by content that is not LF must be treated as a
        # standalone newline, not merged with the following byte.
        self.assertEqual(normalize_bytes(b"a\rX\rb", b"\n"), b"a\nX\nb")

    def test_empty_input(self):
        self.assertEqual(normalize_bytes(b"", b"\n"), b"")

    def test_only_newlines(self):
        self.assertEqual(normalize_bytes(b"\r\n\r\n", b"\n"), b"\n\n")

    def test_binary_passthrough_non_newline_bytes(self):
        # Non-text bytes that are not CR or LF must survive untouched.
        src = bytes([0x00, 0x01, 0x0d, 0x02, 0x0a, 0xff])
        self.assertEqual(normalize_bytes(src, b"\n"), bytes([0x00, 0x01, 0x0a, 0x02, 0x0a, 0xff]))

    def test_invalid_target_raises(self):
        with self.assertRaises(ValueError):
            normalize_bytes(b"a\n", b"\\n")

    def test_invalid_target_empty_raises(self):
        with self.assertRaises(ValueError):
            normalize_bytes(b"a\n", b"")


class TestNormalizeFile(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name: str, data: bytes) -> str:
        path = os.path.join(self.dir, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def _read(self, path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    def test_modifies_crlf_file(self):
        path = self._write("a.txt", b"hello\r\nworld\r\n")
        changed = normalize_file(path, b"\n")
        self.assertTrue(changed)
        self.assertEqual(self._read(path), b"hello\nworld\n")

    def test_returns_false_when_already_canonical(self):
        path = self._write("a.txt", b"hello\nworld\n")
        changed = normalize_file(path, b"\n")
        self.assertFalse(changed)
        self.assertEqual(self._read(path), b"hello\nworld\n")

    def test_returns_false_when_no_newlines(self):
        path = self._write("a.txt", b"no newlines here")
        changed = normalize_file(path, b"\n")
        self.assertFalse(changed)
        self.assertEqual(self._read(path), b"no newlines here")

    def test_temp_file_cleaned_up_on_success(self):
        path = self._write("a.txt", b"a\r\nb")
        normalize_file(path, b"\n")
        tmp = path + ".nlrtmp"
        self.assertFalse(os.path.exists(tmp))

    def test_default_target_is_lf(self):
        path = self._write("a.txt", b"a\r\nb\r")
        normalize_file(path)
        self.assertEqual(self._read(path), b"a\nb\n")


class TestNormalizeFiles(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name: str, data: bytes) -> str:
        path = os.path.join(self.dir, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def _read(self, path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    def test_multiple_files_mixed_endings(self):
        a = self._write("a.txt", b"x\r\ny")
        b = self._write("b.txt", b"x\ry")
        c = self._write("c.txt", b"x\ny")
        results = normalize_files([a, b, c], b"\n")
        self.assertTrue(results[a])
        self.assertTrue(results[b])
        self.assertFalse(results[c])
        self.assertEqual(self._read(a), b"x\ny")
        self.assertEqual(self._read(b), b"x\ny")
        self.assertEqual(self._read(c), b"x\ny")

    def test_accepts_generator(self):
        a = self._write("a.txt", b"x\r\ny")
        b = self._write("b.txt", b"x\ry")
        results = normalize_files(iter([a, b]), b"\n")
        self.assertTrue(results[a])
        self.assertTrue(results[b])

    def test_raises_on_missing_file_after_processing_others(self):
        a = self._write("a.txt", b"x\r\ny")
        missing = os.path.join(self.dir, "does_not_exist.txt")
        with self.assertRaises(FileNotFoundError):
            normalize_files([a, missing], b"\n")
        # The valid file should still have been processed.
        self.assertEqual(self._read(a), b"x\ny")

    def test_invalid_target_raises_before_any_io(self):
        a = self._write("a.txt", b"x\r\ny")
        with self.assertRaises(ValueError):
            normalize_files([a], b"\\n")
        # File untouched.
        self.assertEqual(self._read(a), b"x\r\ny")


if __name__ == "__main__":
    unittest.main()
