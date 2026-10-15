"""newline-normalizer-rewriter: in-place newline normalization."""

from .core import (
    normalize_file,
    normalize_files,
    normalize_bytes,
)

__all__ = [
    "normalize_file",
    "normalize_files",
    "normalize_bytes",
]
