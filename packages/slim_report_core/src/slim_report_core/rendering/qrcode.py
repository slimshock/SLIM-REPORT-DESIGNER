"""Deterministic QR-style matrix helpers."""

from __future__ import annotations

QR_GRID_SIZE = 29
QR_QUIET_ZONE = 4
QR_DATA_SIZE = 21


def qr_module_matrix(value: object) -> list[list[bool]]:
    """Return a stable QR-like matrix with quiet zone and finder patterns.

    This is a dependency-free visual fallback, not a standards-compliant QR encoder.
    """

    text = str(value or "QR Code")
    seed = _stable_hash(text)
    matrix = [[False for _ in range(QR_GRID_SIZE)] for _ in range(QR_GRID_SIZE)]

    finder_origins = [
        (QR_QUIET_ZONE, QR_QUIET_ZONE),
        (QR_QUIET_ZONE, QR_QUIET_ZONE + QR_DATA_SIZE - 7),
        (QR_QUIET_ZONE + QR_DATA_SIZE - 7, QR_QUIET_ZONE),
    ]
    for row, col in finder_origins:
        _draw_finder(matrix, row, col)

    timing_row = QR_QUIET_ZONE + 6
    timing_col = QR_QUIET_ZONE + 6
    for index in range(8, QR_DATA_SIZE - 8):
        enabled = index % 2 == 0
        matrix[timing_row][QR_QUIET_ZONE + index] = enabled
        matrix[QR_QUIET_ZONE + index][timing_col] = enabled

    for inner_row in range(QR_DATA_SIZE):
        for inner_col in range(QR_DATA_SIZE):
            row = QR_QUIET_ZONE + inner_row
            col = QR_QUIET_ZONE + inner_col
            if _reserved(inner_row, inner_col):
                continue
            char_code = ord(text[(inner_row * QR_DATA_SIZE + inner_col) % len(text)])
            mixed = (
                seed
                ^ ((inner_row + 1) * 0x45D9F3B)
                ^ ((inner_col + 1) * 0x27D4EB2D)
                ^ (char_code * (inner_row + inner_col + 1))
            ) & 0xFFFFFFFF
            matrix[row][col] = mixed % 7 in {0, 2, 5}

    return matrix


def _stable_hash(value: str) -> int:
    seed = 2166136261
    for char in value:
        seed ^= ord(char)
        seed = (seed * 16777619) & 0xFFFFFFFF
    return seed


def _draw_finder(matrix: list[list[bool]], top: int, left: int) -> None:
    for row in range(7):
        for col in range(7):
            edge = row in {0, 6} or col in {0, 6}
            core = 2 <= row <= 4 and 2 <= col <= 4
            matrix[top + row][left + col] = edge or core


def _reserved(row: int, col: int) -> bool:
    finder_origins = [(0, 0), (0, QR_DATA_SIZE - 7), (QR_DATA_SIZE - 7, 0)]
    for finder_row, finder_col in finder_origins:
        if finder_row - 1 <= row <= finder_row + 7 and finder_col - 1 <= col <= finder_col + 7:
            return True
    return row == 6 or col == 6
