"""Theme and design constants for SpyQBank."""

import flet as ft

# Colors
PRIMARY = "#1E40AF"        # Deep Blue
PRIMARY_LIGHT = "#3B82F6"  # Bright Blue
PRIMARY_DARK = "#1E3A8A"   # Darker Navy
SECONDARY = "#0D9488"      # Teal
BG_DARK = "#0F172A"        # Slate 900
BG_CARD_DARK = "#1E293B"   # Slate 800
BG_LIGHT = "#F8FAFC"       # Slate 50
BG_CARD_LIGHT = "#FFFFFF"  # White
TEXT_MAIN = "#0F172A"
TEXT_MUTED = "#64748B"
BORDER_COLOR = "#E2E8F0"
BORDER_DARK = "#334155"

# Badge colors
COLOR_Q1 = "#2563EB"       # Blue for Q1
COLOR_Q2 = "#059669"       # Green for Q2
COLOR_Q3 = "#D97706"       # Amber for Q3
COLOR_Q4 = "#DC2626"       # Red for Q4

def get_question_color(q_num: int) -> str:
    if q_num == 1:
        return COLOR_Q1
    elif q_num == 2:
        return COLOR_Q2
    elif q_num == 3:
        return COLOR_Q3
    elif q_num == 4:
        return COLOR_Q4
    return PRIMARY_LIGHT
