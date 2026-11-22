"""Small helper shared by the kit tools: print ticks and crosses safely.

Some Windows terminals (and Git Bash) cannot show the tick and cross
characters. If the terminal cannot encode them, we fall back to plain text
so the tools never crash just because of a symbol.
"""
import sys


def _can_encode(text):
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

if _can_encode("✓✗⚠"):
    TICK, CROSS, WARN = "✓", "✗", "⚠"
else:
    TICK, CROSS, WARN = "[ok]", "[X]", "[!]"
