"""Jetons de design et feuilles de style : themes sombre et clair.

Toutes les couleurs vivent ici. Aucune valeur hexadecimale ne doit
apparaitre ailleurs dans l'interface : changer de theme reste ainsi une
operation locale et sure.
"""

from __future__ import annotations

from dataclasses import dataclass

from transcribe_ai.config.settings import Theme


@dataclass(frozen=True)
class Palette:
    """Jetons de couleur d'un theme."""

    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    primary: str
    primary_hover: str
    primary_text: str
    success: str
    warning: str
    danger: str
    sidebar: str
    sidebar_text: str
    sidebar_active: str


DARK = Palette(
    bg="#0f1117",
    surface="#171a23",
    surface_alt="#1e222e",
    border="#2a2f3d",
    text="#e8eaf0",
    text_muted="#8b91a3",
    primary="#6c5ce7",
    primary_hover="#7d6ff0",
    primary_text="#ffffff",
    success="#22c55e",
    warning="#f59e0b",
    danger="#ef4444",
    sidebar="#12141c",
    sidebar_text="#a7adbf",
    sidebar_active="#6c5ce7",
)

LIGHT = Palette(
    bg="#f5f6fa",
    surface="#ffffff",
    surface_alt="#eef0f6",
    border="#dfe2ec",
    text="#1a1d26",
    text_muted="#6b7185",
    primary="#6c5ce7",
    primary_hover="#5a4bd6",
    primary_text="#ffffff",
    success="#16a34a",
    warning="#d97706",
    danger="#dc2626",
    sidebar="#ffffff",
    sidebar_text="#4b5163",
    sidebar_active="#6c5ce7",
)

PALETTES: dict[str, Palette] = {"dark": DARK, "light": LIGHT}


def palette_for(theme: Theme | str) -> Palette:
    key = theme.value if isinstance(theme, Theme) else str(theme)
    if key == "system":  # pas de detection fiable multiplateforme : sombre par defaut
        key = "dark"
    return PALETTES.get(key, DARK)


def build_stylesheet(theme: Theme | str = Theme.DARK) -> str:
    """Genere la feuille de style Qt complete pour le theme demande."""
    c = palette_for(theme)
    return f"""
/* ---------- Base ---------- */
QWidget {{
    background-color: {c.bg};
    color: {c.text};
    font-family: 'Segoe UI', 'Inter', 'Ubuntu', sans-serif;
    font-size: 14px;
}}
QMainWindow, QDialog {{ background-color: {c.bg}; }}
/* Les libellés et cases à cocher doivent laisser voir le fond de leur carte. */
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}

/* ---------- Sidebar ---------- */
#Sidebar {{
    background-color: {c.sidebar};
    border-right: 1px solid {c.border};
}}
#SidebarLogo {{
    color: {c.text};
    font-size: 17px;
    font-weight: 700;
    padding: 20px 18px 6px 18px;
}}
#SidebarVersion {{
    color: {c.text_muted};
    font-size: 11px;
    padding: 0 18px 18px 18px;
}}
QPushButton#NavButton {{
    background-color: transparent;
    color: {c.sidebar_text};
    border: none;
    border-left: 3px solid transparent;
    text-align: left;
    padding: 12px 16px;
    font-size: 14px;
    border-radius: 0;
}}
QPushButton#NavButton:hover {{
    background-color: {c.surface_alt};
    color: {c.text};
}}
QPushButton#NavButton:checked {{
    background-color: {c.surface};
    color: {c.text};
    border-left: 3px solid {c.sidebar_active};
    font-weight: 600;
}}

/* ---------- Cards ---------- */
#Card {{
    background-color: {c.surface};
    border: 1px solid {c.border};
    border-radius: 12px;
}}
#CardTitle {{ font-size: 15px; font-weight: 600; color: {c.text}; }}
#CardSubtitle {{ font-size: 12px; color: {c.text_muted}; }}
#PageTitle {{ font-size: 24px; font-weight: 700; color: {c.text}; }}
#PageSubtitle {{ font-size: 13px; color: {c.text_muted}; }}
#StatValue {{ font-size: 26px; font-weight: 700; color: {c.primary}; }}
#StatLabel {{ font-size: 12px; color: {c.text_muted}; }}
#Muted {{ color: {c.text_muted}; }}

/* ---------- Boutons ---------- */
QPushButton {{
    background-color: {c.surface_alt};
    color: {c.text};
    border: 1px solid {c.border};
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 500;
}}
QPushButton:hover {{ background-color: {c.border}; }}
QPushButton:disabled {{ color: {c.text_muted}; background-color: {c.surface}; }}
QPushButton#Primary {{
    background-color: {c.primary};
    color: {c.primary_text};
    border: none;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background-color: {c.primary_hover}; }}
QPushButton#Primary:disabled {{ background-color: {c.border}; color: {c.text_muted}; }}
QPushButton#Danger {{
    background-color: transparent;
    color: {c.danger};
    border: 1px solid {c.danger};
}}
QPushButton#Danger:hover {{ background-color: {c.danger}; color: #ffffff; }}
QPushButton#Ghost {{ background-color: transparent; border: none; color: {c.text_muted}; }}
QPushButton#Ghost:hover {{ color: {c.text}; }}

/* ---------- Champs ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {c.surface_alt};
    border: 1px solid {c.border};
    border-radius: 8px;
    padding: 9px 12px;
    selection-background-color: {c.primary};
    color: {c.text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {c.primary}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
/* Les fleches des compteurs doivent rester dans l'arrondi du champ. */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 18px;
    border: none;
    background: transparent;
    margin-right: 4px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {c.text_muted};
    width: 0; height: 0;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {c.text_muted};
    width: 0; height: 0;
}}
QComboBox QAbstractItemView {{
    background-color: {c.surface};
    border: 1px solid {c.border};
    selection-background-color: {c.primary};
    color: {c.text};
}}

/* ---------- Progression ---------- */
QProgressBar {{
    background-color: {c.surface_alt};
    border: none;
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background-color: {c.primary}; border-radius: 5px; }}

/* ---------- Badges ---------- */
/* La forme est partagee par toutes les variantes : l'objectName porte la
   couleur, ces regles portent la geometrie. */
#Badge, #BadgeSuccess, #BadgeWarning, #BadgeDanger, #BadgeNeutral, #BadgeInfo {{
    border-radius: 10px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
}}
#BadgeSuccess {{ background-color: {c.success}; color: #ffffff; }}
#BadgeWarning {{ background-color: {c.warning}; color: #ffffff; }}
#BadgeDanger  {{ background-color: {c.danger}; color: #ffffff; }}
#BadgeNeutral {{ background-color: {c.surface_alt}; color: {c.text_muted}; }}
#BadgeInfo    {{ background-color: {c.primary}; color: {c.primary_text}; }}

/* ---------- Tables ---------- */
QTableWidget, QTableView {{
    background-color: {c.surface};
    border: 1px solid {c.border};
    border-radius: 10px;
    gridline-color: {c.border};
    selection-background-color: {c.primary};
    selection-color: {c.primary_text};
}}
QHeaderView::section {{
    background-color: {c.surface_alt};
    color: {c.text_muted};
    border: none;
    border-bottom: 1px solid {c.border};
    padding: 10px;
    font-weight: 600;
}}
QTableWidget::item {{ padding: 6px; }}

/* ---------- Divers ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c.border}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {c.text_muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {c.border}; border-radius: 5px; min-width: 30px; }}
QToolTip {{
    background-color: {c.surface};
    color: {c.text};
    border: 1px solid {c.border};
    padding: 6px;
    border-radius: 6px;
}}
QCheckBox {{ spacing: 8px; }}
#Separator {{ background-color: {c.border}; max-height: 1px; border: none; }}
#Toast {{
    background-color: {c.surface};
    border: 1px solid {c.border};
    border-radius: 10px;
    padding: 12px 16px;
}}
QTabWidget::pane {{ border: 1px solid {c.border}; border-radius: 10px; }}
QTabBar::tab {{
    background: transparent;
    color: {c.text_muted};
    padding: 9px 18px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {c.text}; border-bottom: 2px solid {c.primary}; font-weight: 600; }}
"""
