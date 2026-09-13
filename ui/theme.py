"""Shared colors and small Tk styling helpers for the dashboard."""

BG_MAIN = "#050B14"
BG_PANEL = "#0F1622"
BG_SECONDARY = "#121B29"
BG_TOOLBAR = "#162132"
BG_HEADER = "#1A2433"
BORDER_GOLD = "#8A775A"
ACCENT_GOLD = "#B79A6A"
TEXT_PRIMARY = "#E8ECF3"
TEXT_SECONDARY = "#9AA4B2"
SELECTED = "#35425A"
ACTIVE_BG = "#123824"
ACTIVE_FG = "#BDDAC9"
INACTIVE_BG = "#3D1818"
INACTIVE_FG = "#E1BDBD"
NEUTRAL_BG = "#263246"
DISABLED_BG = "#1B2028"
DISABLED_FG = "#818995"
DISABLED_BORDER = "#4F493F"
ADD_BG = "#183039"
REMOVE_BG = "#38212C"
START_BG = "#193B2B"
STOP_BG = "#3D2427"
RESTART_BG = "#3A3024"
ENABLE_BG = "#223248"
DISABLE_BG = "#282D35"

BORDER = dict(highlightbackground=BORDER_GOLD, highlightcolor=ACCENT_GOLD,
              highlightthickness=1, bd=0)
INPUT = dict(BORDER, bg=BG_MAIN, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
             selectbackground=SELECTED, selectforeground=TEXT_PRIMARY)
BUTTON = dict(BORDER, activebackground=BG_HEADER, activeforeground=TEXT_PRIMARY,
              disabledforeground=DISABLED_FG)
RADIO = dict(BORDER, indicatoron=False, selectcolor=SELECTED,
             activebackground=BG_HEADER, activeforeground=TEXT_PRIMARY,
             relief="flat", offrelief="flat", padx=10, pady=5)
MENU = dict(bg=BG_PANEL, fg=TEXT_PRIMARY, activebackground=SELECTED,
            activeforeground=TEXT_PRIMARY, relief="flat", bd=0)


def set_button_state(button, state, **options):
    """Keep disabled controls legible and restore their original action tint."""
    if not hasattr(button, "theme_background"):
        button.theme_background = button.cget("background")
    enabled = state != "disabled"
    button.configure(
        state=state,
        bg=button.theme_background if enabled else DISABLED_BG,
        highlightbackground=BORDER_GOLD if enabled else DISABLED_BORDER,
        **options,
    )
