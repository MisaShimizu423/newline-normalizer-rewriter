# newline-normalizer-rewriter

In-place converts CRLF, CR, or LF line endings to a single canonical form across a set of files. Standard library only, no third-party dependencies.

## Usage

```python
import tempfile, os
from newline_normalizer_rewriter import normalize_file, normalize_files, normalize_bytes

d = tempfile.mkdtemp()
p = os.path.join(d, "file.txt")
with open(p, "wb") as f:
    f.write(b"hello\r\nworld\r")

# Normalize a single file to LF (the default target).
modified = normalize_file(p)
# modified is True if the file changed, False if it was already LF-only.

# Normalize many files to CRLF.
results = normalize_files([p], target=b"\r\n")
# results is {p: True/False}

# Pure function over bytes, no file I/O.
normalized = normalize_bytes(b"hello\r\nworld\r", target=b"\n")
# -> b"hello\nworld\n"
```

`target` must be one of `b"\r\n"`, `b"\r"`, or `b"\n"`; anything else raises `ValueError`.

## Why

Source files that travel between operating systems accumulate mixed line endings: a file edited on Windows, then touched on macOS, then committed from Linux can contain CRLF, CR, and LF in the same bytes. Diff tools and some parsers treat these as significant, so the first step of any cleanup is to pick one canonical form and apply it everywhere.

This library does exactly that and nothing else. It does not strip trailing whitespace, collapse blank lines, or re-encode the file. The trade-off is simplicity and determinism over convenience: if you want those other transforms, compose them yourself.

The canonical form must be a single newline sequence, so `target` is validated to one of the three recognised byte sequences. A typo like `b"\\n"` (backslash-n, two bytes) is rejected rather than silently written into every line break in the file.

## Edge cases

- **CRLF ordering matters.** The scan checks for CRLF (two bytes) before CR or LF. If it checked LF first, a CRLF pair would be split into two separate replacements and each file would grow spurious blank lines. The tests cover this directly.
- **Lone CR is a newline.** A CR not followed by LF is still normalised. This matches classic Mac OS line endings. If your file contains CR used for non-newline purposes (rare today), it will still be converted.
- **Entire file is read into memory.** Normalisation is a streaming-friendly operation in principle, but this implementation reads the whole file, normalises, and writes via a temp file plus atomic `os.replace`. This keeps the on-disk update atomic and the code simple. The cost is memory proportional to file size, which is the right call for source and config files.
- **Non-text bytes pass through.** We do not validate or transcode the file. A binary file containing `0x0d` or `0x0a` will have those bytes rewritten; this is expected because the library has no notion of encoding.
- **I/O errors in batch mode.** `normalize_files` processes every file it can and records `False` for any that error, then re-raises the first error after the batch completes. This is a deliberate choice so a single missing file does not abort an entire batch partway through.

## Running the tests

```
PYTHONPATH=src python -m unittest discover -s tests
```
