"""Core newline-normalization logic.

We operate on bytes, not text. The motivation: Python's text-mode I/O on
some platforms silently translates newlines, which would make it impossible
to write a test that is deterministic across operating systems. By reading
in binary and writing in binary we get full control and the exact bytes on
disk are exactly what we put there.

Canonical forms we accept as the 'target' are the three single-byte sequences
b'\r\n', b'\r', and b'\n'. Anything else raises ValueError immediately so a
typo does not silently corrupt files.

Non-newline bytes are passed through untouched. We do not attempt to
validate encoding -- a file may be invalid UTF-8 and still have its newline
sequences normalized.
"""

from __future__ import annotations

import os


# Recognised newline sequences, longest first so the scan below matches
# CRLF before it would match a lone CR or LF.
_NEWLINES = (b"\r\n", b"\r", b"\n")


def _validate_target(target: bytes) -> None:
    if target not in _NEWLINES:
        raise ValueError(
            "target must be one of b'\\r\\n', b'\\r', b'\\n'; got %r" % (target,)
        )


def normalize_bytes(data: bytes, target: bytes = b"\n") -> bytes:
    """Return *data* with every CR, LF, or CRLF replaced by *target*.

    The scan is a single left-to-right pass. At each position we check for
    CRLF first (two bytes), then CR, then LF. This ordering is essential:
    if we checked LF before CRLF we would break a CRLF into two separate
    replacements and emit a spurious extra newline.

    Non-newline bytes are copied verbatim, so a file with no newline sequences
    at all returns byte-for-byte identical.
    """
    _validate_target(target)

    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        if data[i:i + 2] == b"\r\n":
            out += target
            i += 2
            continue
        b = data[i:i + 1]
        if b == b"\r" or b == b"\n":
            out += target
            i += 1
            continue
        out += b
        i += 1
    return bytes(out)


def normalize_file(
    path: str | os.PathLike[str],
    target: bytes = b"\n",
) -> bool:
    """Normalize the newline sequences of the file at *path* in place.

    Returns True if the file was modified, False if it already contained
    only the target newline (or no newlines at all).

    We read the entire file into memory. This is a deliberate trade-off: the
    alternative is a streaming scan with a one-byte lookahead buffer, which
    is correct but significantly harder to reason about for the CRLF case.
    The cost is memory proportional to file size, which is acceptable for
    source-code and config files -- the intended use case.
    """
    _validate_target(target)

    with open(path, "rb") as f:
        original = f.read()

    normalized = normalize_bytes(original, target)
    if normalized == original:
        return False

    # Write-then-replace rather than truncate-in-place: on some platforms an
    # open handle with truncation can interact badly with concurrent readers.
    # A temp file followed by atomic rename sidesteps that entirely.
    tmp = str(path) + ".nlrtmp"
    with open(tmp, "wb") as f:
        f.write(normalized)
    os.replace(tmp, path)
    return True


def normalize_files(
    paths,
    target: bytes = b"\n",
):
    """Normalize newline sequences across many files.

    *paths* is any iterable of path-like objects. We materialise it into a
    list so that we can report a stable count even if the iterable is a
    generator (and so a partial failure does not leave the generator half
    consumed with no way to report what was done).

    Returns a dict mapping each processed path (as a string) to a bool
    indicating whether that file was modified. We do not raise on a single
    file's I/O error; instead we re-raise only after attempting every file so
    that a batch job reports as much progress as possible. For simplicity
    and predictability the first error encountered is re-raised after the
    iteration completes.
    """
    _validate_target(target)

    materialised = list(paths)
    results: dict[str, bool] = {}
    first_error: Exception | None = None

    for p in materialised:
        key = os.fspath(p)
        try:
            results[key] = normalize_file(p, target)
        except Exception as exc:  # noqa: BLE001 - surface caller-visible errors
            results[key] = False
            if first_error is None:
                first_error = exc

    if first_error is not None:
        raise first_error
    return results
