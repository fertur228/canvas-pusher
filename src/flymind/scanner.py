"""Compatibility name for the shared, strict Canvas scanner."""
from src.core.scanner import AsyncCanvasScanner, ScanFailure


class ReliableCanvasScanner(AsyncCanvasScanner):
    pass
