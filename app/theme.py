# cprc_app/app/theme.py
THEME = {
    "gradient_bg": "linear-gradient(170deg, #B2DCFF, #00223E)",
    "light_blue_bg": "#B2DCFF",
    "mid_blue_bg": "#1796FF",
    "dark_blue_bg": "#00223E",
    "border_subtle": "1px solid rgba(255,255,255,0.15)",
    "shadow_md": "0 8px 24px rgba(0,0,0,0.15)",
    "shadow_lg": "0 10px 28px rgba(0,0,0,0.22)",
    "on_dark": "#B2DCFF",
    "font_heading": "var(--font-heading)",
    "font_body": "var(--font-body)",
    "font_mono": "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
    "weight_reg": 400,
    "weight_semibold": 600,
    "weight_bold": 700,
    "weight_extrabold": 800,
}

CARD_BASE = {
    "background": THEME["dark_blue_bg"],
    "border": THEME["border_subtle"],
    "color": THEME["on_dark"],
    "boxShadow": THEME["shadow_md"],
    "borderRadius": "14px",
    "fontFamily": THEME["font_body"],
}

PILL_CARD = {
    **CARD_BASE,
    "borderRadius": "14px",
    "padding": "2px 6px",
    "width": "fit-content",
    "maxWidth": "100%",
}
