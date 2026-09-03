from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Release UI shows the three core theme names first, then keeps the extra palettes numbered.
THEME_INTERNAL_NAMES = ('Classic',
 'Light',
 'Full Dark',
 'Web Blue',
 'Cobweb Dark',
 'Spider Web',
 'Halloween Purple',
 'Comic Dark',
 'Hero Crimson',
 'Gotham Night',
 'Halloween Cobweb',
 'Abstract Blue',
 'Realistic Web',
 'Winter Snow')
THEME_NAMES = ('Classic',
 'Light',
 'Full Dark',
 'Theme 1',
 'Theme 2',
 'Theme 3',
 'Theme 4',
 'Theme 5',
 'Theme 6',
 'Theme 7',
 'Theme 8',
 'Theme 9',
 'Theme 10',
 'Theme 11')
THEME_DISPLAY_TO_INTERNAL = {'Classic': 'Classic',
 'Light': 'Light',
 'Full Dark': 'Full Dark',
 'Theme 1': 'Web Blue',
 'Theme 2': 'Cobweb Dark',
 'Theme 3': 'Spider Web',
 'Theme 4': 'Halloween Purple',
 'Theme 5': 'Comic Dark',
 'Theme 6': 'Hero Crimson',
 'Theme 7': 'Gotham Night',
 'Theme 8': 'Halloween Cobweb',
 'Theme 9': 'Abstract Blue',
 'Theme 10': 'Realistic Web',
 'Theme 11': 'Winter Snow'}
THEME_INTERNAL_TO_DISPLAY = {'Abstract Blue': 'Theme 9',
 'Classic': 'Classic',
 'Cobweb Dark': 'Theme 2',
 'Comic Dark': 'Theme 5',
 'Full Dark': 'Full Dark',
 'Gotham Night': 'Theme 7',
 'Halloween Cobweb': 'Theme 8',
 'Halloween Purple': 'Theme 4',
 'Hero Crimson': 'Theme 6',
 'Light': 'Light',
 'Realistic Web': 'Theme 10',
 'Spider Web': 'Theme 3',
 'Web Blue': 'Theme 1',
 'Winter Snow': 'Theme 11'}
DEFAULT_THEME = "Classic"
DEFAULT_THEME_KEY = "Classic"

PALETTES = {'Abstract Blue': {'accent': '#315A85',
                   'accent_hover': '#3F719F',
                   'accent_pressed': '#244261',
                   'bad': '#FF9A9A',
                   'bg': '#050A18',
                   'border': '#335F95',
                   'brand': '#DCEBFA',
                   'button': '#142335',
                   'button_hover': '#1F334A',
                   'button_pressed': '#0B1725',
                   'byline': '#BDD2E8',
                   'fg': '#EEF6FF',
                   'field': '#060D1E',
                   'header': '#030611',
                   'muted': '#B6C9E8',
                   'notice': '#2768B8',
                   'panel': '#0A1226',
                   'panel2': '#101D3A',
                   'select': '#245EA3',
                   'soft': '#7E93B8',
                   'warn': '#D7EBFF'},
 'Classic': {'accent': '#3B4048',
             'accent_hover': '#464B54',
             'accent_pressed': '#2B3037',
             'bad': '#FF9A9A',
             'bg': '#171717',
             'border': '#555555',
             'brand': '#DCE6F2',
             'button': '#30343B',
             'button_hover': '#3A3D45',
             'button_pressed': '#23262C',
             'byline': '#C7CCD6',
             'fg': '#F2F2F2',
             'field': '#2B2B2B',
             'header': '#101318',
             'muted': '#BDBDBD',
             'notice': '#464B54',
             'panel': '#202020',
             'panel2': '#252526',
             'select': '#3F424A',
             'soft': '#8E8E8E',
             'warn': '#DCE6F2'},
 'Cobweb Dark': {'accent': '#3C3D40',
                 'accent_hover': '#4B4C50',
                 'accent_pressed': '#2A2B2E',
                 'bad': '#FF9A9A',
                 'bg': '#101112',
                 'border': '#56585D',
                 'brand': '#F5F5F5',
                 'button': '#28292C',
                 'button_hover': '#34363A',
                 'button_pressed': '#1C1D20',
                 'byline': '#D0D0D0',
                 'fg': '#F0F0F0',
                 'field': '#121315',
                 'header': '#0A0A0B',
                 'muted': '#B7B7B7',
                 'notice': '#4B4C50',
                 'panel': '#191A1C',
                 'panel2': '#242527',
                 'select': '#484A4F',
                 'soft': '#888888',
                 'warn': '#F5F5F5'},
 'Comic Dark': {'accent': '#464E62',
                'accent_hover': '#596177',
                'accent_pressed': '#333A4A',
                'bad': '#FF9A9A',
                'bg': '#101116',
                'border': '#596275',
                'brand': '#EEF2F8',
                'button': '#242B38',
                'button_hover': '#303848',
                'button_pressed': '#1A202B',
                'byline': '#C9D0DC',
                'fg': '#F2F4F7',
                'field': '#11131A',
                'header': '#0C0D12',
                'muted': '#C0C6D0',
                'notice': '#AFC1DD',
                'panel': '#181B22',
                'panel2': '#212631',
                'select': '#45536E',
                'soft': '#8B94A3',
                'warn': '#D8A0A0'},
 'Full Dark': {'accent': '#2A2A2A',
               'accent_hover': '#333333',
               'accent_pressed': '#1F1F1F',
               'bad': '#FF9A9A',
               'bg': '#0E0E0E',
               'border': '#4A4A4A',
               'brand': '#F5F5F5',
               'button': '#222222',
               'button_hover': '#2E2E2E',
               'button_pressed': '#181818',
               'byline': '#D0D0D0',
               'fg': '#F5F5F5',
               'field': '#111111',
               'header': '#0B0B0B',
               'muted': '#B8B8B8',
               'notice': '#333333',
               'panel': '#151515',
               'panel2': '#1B1B1B',
               'select': '#3A3A3A',
               'soft': '#888888',
               'warn': '#F5F5F5'},
 'Gotham Night': {'accent': '#3C4656',
                  'accent_hover': '#4E5A6D',
                  'accent_pressed': '#2B3442',
                  'bad': '#FF9A9A',
                  'bg': '#080A0D',
                  'border': '#555E70',
                  'brand': '#EEF2F6',
                  'button': '#1D2430',
                  'button_hover': '#293241',
                  'button_pressed': '#141922',
                  'byline': '#D2D8E0',
                  'fg': '#F2F4F7',
                  'field': '#0B0E13',
                  'header': '#030406',
                  'muted': '#B9C0CA',
                  'notice': '#B5C3D5',
                  'panel': '#11141A',
                  'panel2': '#191E27',
                  'select': '#455367',
                  'soft': '#858F9D',
                  'warn': '#D4A0A7'},
 'Halloween Cobweb': {'accent': '#4D344F',
                      'accent_hover': '#654467',
                      'accent_pressed': '#38253A',
                      'bad': '#FF9A9A',
                      'bg': '#0B0B0D',
                      'border': '#6B5A73',
                      'brand': '#FFF0FF',
                      'button': '#241B27',
                      'button_hover': '#33253A',
                      'button_pressed': '#19111D',
                      'byline': '#D8CEE2',
                      'fg': '#F7F2FF',
                      'field': '#0E0C10',
                      'header': '#050506',
                      'muted': '#CBBFD5',
                      'notice': '#654467',
                      'panel': '#161417',
                      'panel2': '#211E24',
                      'select': '#5A3A5F',
                      'soft': '#9D90AA',
                      'warn': '#FFF0FF'},
 'Halloween Purple': {'accent': '#4A3F68',
                      'accent_hover': '#5C4D7D',
                      'accent_pressed': '#342B51',
                      'bad': '#FF9A9A',
                      'bg': '#100D1F',
                      'border': '#5A4B8C',
                      'brand': '#EFE8FA',
                      'button': '#231D38',
                      'button_hover': '#30264A',
                      'button_pressed': '#171127',
                      'byline': '#D2C7E5',
                      'fg': '#F3EFFF',
                      'field': '#100C28',
                      'header': '#080616',
                      'muted': '#C8BDE8',
                      'notice': '#5A4A8B',
                      'panel': '#171332',
                      'panel2': '#211A46',
                      'select': '#4B3E89',
                      'soft': '#9489B8',
                      'warn': '#EEE7FF'},
 'Hero Crimson': {'accent': '#573035',
                  'accent_hover': '#6B3D43',
                  'accent_pressed': '#42242A',
                  'bad': '#FF9A9A',
                  'bg': '#120909',
                  'border': '#753237',
                  'brand': '#F3D0D3',
                  'button': '#271518',
                  'button_hover': '#351D21',
                  'button_pressed': '#1B0E10',
                  'byline': '#DAB5B9',
                  'fg': '#F9EFEF',
                  'field': '#100809',
                  'header': '#080304',
                  'muted': '#D0B0B3',
                  'notice': '#D0B0B3',
                  'panel': '#1A0E10',
                  'panel2': '#221316',
                  'select': '#4F3438',
                  'soft': '#9C797D',
                  'warn': '#E1A6AA'},
 'Light': {'accent': '#B7C1CB',
           'accent_hover': '#AEB8C2',
           'accent_pressed': '#98A4AF',
           'bad': '#8B1A1A',
           'bg': '#E8ECEF',
           'border': '#A7B0B9',
           'brand': '#101418',
           'button': '#D9E0E6',
           'button_hover': '#C9D3DC',
           'button_pressed': '#B8C5D0',
           'byline': '#303943',
           'fg': '#14171A',
           'field': '#E4E9EE',
           'header': '#EEF2F5',
           'muted': '#3D454D',
           'notice': '#425466',
           'panel': '#F0F3F6',
           'panel2': '#DCE3E9',
           'select': '#C1CCD6',
           'soft': '#68727C',
           'warn': '#713232'},
 'Realistic Web': {'accent': '#42565F',
                   'accent_hover': '#526B76',
                   'accent_pressed': '#304048',
                   'bad': '#FF9A9A',
                   'bg': '#080A0C',
                   'border': '#5C717A',
                   'brand': '#F1F6F8',
                   'button': '#1C272E',
                   'button_hover': '#283640',
                   'button_pressed': '#121B20',
                   'byline': '#CBD7DD',
                   'fg': '#F3F7FA',
                   'field': '#090D10',
                   'header': '#030405',
                   'muted': '#BAC6CF',
                   'notice': '#4C6A78',
                   'panel': '#12161A',
                   'panel2': '#1A2026',
                   'select': '#405A66',
                   'soft': '#87949E',
                   'warn': '#F7FCFF'},
 'Spider Web': {'accent': '#444444',
                'accent_hover': '#555555',
                'accent_pressed': '#303030',
                'bad': '#FF9A9A',
                'bg': '#060606',
                'border': '#666666',
                'brand': '#FFFFFF',
                'button': '#202020',
                'button_hover': '#2B2B2B',
                'button_pressed': '#151515',
                'byline': '#DADADA',
                'fg': '#F8F8F8',
                'field': '#0A0A0A',
                'header': '#000000',
                'muted': '#CCCCCC',
                'notice': '#555555',
                'panel': '#111111',
                'panel2': '#1D1D1D',
                'select': '#4E4E4E',
                'soft': '#9A9A9A',
                'warn': '#FFFFFF'},
 'Web Blue': {'accent': '#294A6B',
              'accent_hover': '#345D84',
              'accent_pressed': '#1B344F',
              'bad': '#FF9A9A',
              'bg': '#06101F',
              'border': '#355273',
              'brand': '#D5E9FA',
              'button': '#142438',
              'button_hover': '#1E314B',
              'button_pressed': '#0C1929',
              'byline': '#AFC5DC',
              'fg': '#EAF3FF',
              'field': '#071326',
              'header': '#040A14',
              'muted': '#AFC0D8',
              'notice': '#2D4E82',
              'panel': '#0B1628',
              'panel2': '#10213A',
              'select': '#284B78',
              'soft': '#7E91AA',
              'warn': '#CFE6FF'},
 'Winter Snow': {'accent': '#8FB2CB',
                 'accent_hover': '#88AEC9',
                 'accent_pressed': '#719FBD',
                 'bad': '#8B1A1A',
                 'bg': '#E3ECF3',
                 'border': '#7EA1BB',
                 'brand': '#102A42',
                 'button': '#CBDCE8',
                 'button_hover': '#B9CFDF',
                 'button_pressed': '#A8C1D3',
                 'byline': '#2F4A63',
                 'fg': '#0F1F30',
                 'field': '#DDEAF3',
                 'header': '#D5E4EF',
                 'muted': '#384E64',
                 'notice': '#405C72',
                 'panel': '#ECF4F9',
                 'panel2': '#D2E2EE',
                 'select': '#B8D1E5',
                 'soft': '#667D93',
                 'warn': '#724029'}}

# ---------------------------------------------------------------------------
# v5.2.176 additional release palettes
# ---------------------------------------------------------------------------
# Keep the public selector numbered like the earlier extra themes while retaining
# descriptive internal names for maintenance and release notes.
THEME_INTERNAL_NAMES += (
    'Raimi Red & Blue',
    'Symbiote',
    'Venom Purple',
    'Goblin Green',
    'Sandman',
    'Electro',
    'Neon City',
    'PS3 Blue',
)
THEME_NAMES += (
    'Theme 12',
    'Theme 13',
    'Theme 14',
    'Theme 15',
    'Theme 16',
    'Theme 17',
    'Theme 18',
    'Theme 19',
)
THEME_DISPLAY_TO_INTERNAL.update({
    'Theme 12': 'Raimi Red & Blue',
    'Theme 13': 'Symbiote',
    'Theme 14': 'Venom Purple',
    'Theme 15': 'Goblin Green',
    'Theme 16': 'Sandman',
    'Theme 17': 'Electro',
    'Theme 18': 'Neon City',
    'Theme 19': 'PS3 Blue',
})
THEME_INTERNAL_TO_DISPLAY.update({
    'Raimi Red & Blue': 'Theme 12',
    'Symbiote': 'Theme 13',
    'Venom Purple': 'Theme 14',
    'Goblin Green': 'Theme 15',
    'Sandman': 'Theme 16',
    'Electro': 'Theme 17',
    'Neon City': 'Theme 18',
    'PS3 Blue': 'Theme 19',
})

PALETTES.update({
    'Raimi Red & Blue': {
        'accent': '#A6323D', 'accent_hover': '#C33D49', 'accent_pressed': '#78252D',
        'bad': '#FF9A9A', 'bg': '#07111E', 'border': '#3C5674', 'brand': '#EAF3FF',
        'button': '#14253A', 'button_hover': '#1C334F', 'button_pressed': '#0D1A2A',
        'byline': '#B9CCE3', 'fg': '#F4F7FB', 'field': '#091627', 'header': '#040A12',
        'muted': '#B7C4D3', 'notice': '#5C84B5', 'panel': '#0D1B2D', 'panel2': '#14263D',
        'select': '#793947', 'soft': '#8293A8', 'warn': '#F0C7CB',
    },
    'Symbiote': {
        'accent': '#AAB0B7', 'accent_hover': '#C2C7CC', 'accent_pressed': '#777D83',
        'bad': '#FF9A9A', 'bg': '#030303', 'border': '#5F6368', 'brand': '#FFFFFF',
        'button': '#171819', 'button_hover': '#242628', 'button_pressed': '#0C0D0E',
        'byline': '#D3D6D9', 'fg': '#F7F7F7', 'field': '#070808', 'header': '#000000',
        'muted': '#BFC2C5', 'notice': '#B9BEC4', 'panel': '#0D0E0F', 'panel2': '#161719',
        'select': '#474A4E', 'soft': '#8A8E92', 'warn': '#FFFFFF',
    },
    'Venom Purple': {
        'accent': '#6F3C92', 'accent_hover': '#8650AB', 'accent_pressed': '#4D2868',
        'bad': '#FF9A9A', 'bg': '#09060D', 'border': '#704F82', 'brand': '#F2E8FA',
        'button': '#201527', 'button_hover': '#30203A', 'button_pressed': '#150D1A',
        'byline': '#D6C3E1', 'fg': '#F8F3FB', 'field': '#0D0812', 'header': '#050307',
        'muted': '#C7B8D0', 'notice': '#9868B4', 'panel': '#15101A', 'panel2': '#211729',
        'select': '#57316F', 'soft': '#9685A0', 'warn': '#F1DDFB',
    },
    'Goblin Green': {
        'accent': '#347A4B', 'accent_hover': '#42965E', 'accent_pressed': '#245736',
        'bad': '#FF9A9A', 'bg': '#06100A', 'border': '#476958', 'brand': '#E5F4E9',
        'button': '#13251A', 'button_hover': '#1B3425', 'button_pressed': '#0B180F',
        'byline': '#BED8C6', 'fg': '#F0F7F2', 'field': '#08140D', 'header': '#030804',
        'muted': '#B6CABD', 'notice': '#61A979', 'panel': '#0D1B12', 'panel2': '#14271B',
        'select': '#2D6842', 'soft': '#819689', 'warn': '#D9E8B8',
    },
    'Sandman': {
        'accent': '#9A724B', 'accent_hover': '#B0875F', 'accent_pressed': '#6F5135',
        'bad': '#FFAAAA', 'bg': '#17110C', 'border': '#765D45', 'brand': '#F5E3CE',
        'button': '#302217', 'button_hover': '#423022', 'button_pressed': '#21170F',
        'byline': '#DDC4A8', 'fg': '#FAF2E8', 'field': '#1D150E', 'header': '#0E0A07',
        'muted': '#D0B99F', 'notice': '#C69A6B', 'panel': '#241A12', 'panel2': '#332419',
        'select': '#745338', 'soft': '#A58F78', 'warn': '#F0C78F',
    },
    'Electro': {
        'accent': '#C7AB22', 'accent_hover': '#DFC637', 'accent_pressed': '#8E7918',
        'bad': '#FF9A9A', 'bg': '#070A0D', 'border': '#6F682F', 'brand': '#FFF2A6',
        'button': '#202116', 'button_hover': '#30311D', 'button_pressed': '#15160E',
        'byline': '#D8D1A2', 'fg': '#F7F6EB', 'field': '#0B0E10', 'header': '#030506',
        'muted': '#C5C3AD', 'notice': '#D7BD37', 'panel': '#121619', 'panel2': '#1C211F',
        'select': '#5D5521', 'soft': '#97947B', 'warn': '#FFF08A',
    },
    'Neon City': {
        'accent': '#00A6B8', 'accent_hover': '#18C1D2', 'accent_pressed': '#007483',
        'bad': '#FF8EA8', 'bg': '#060713', 'border': '#315A74', 'brand': '#FF8DD8',
        'button': '#101A2A', 'button_hover': '#17283D', 'button_pressed': '#0A111D',
        'byline': '#B5CAE4', 'fg': '#F1F7FF', 'field': '#080B18', 'header': '#03040B',
        'muted': '#AFC0D7', 'notice': '#3CD4E5', 'panel': '#0D1222', 'panel2': '#151C31',
        'select': '#124F67', 'soft': '#788DA8', 'warn': '#FF9EDD',
    },
    'PS3 Blue': {
        'accent': '#35688F', 'accent_hover': '#447FA9', 'accent_pressed': '#274A67',
        'bad': '#FF9A9A', 'bg': '#07101A', 'border': '#3D617D', 'brand': '#DDEFFF',
        'button': '#132233', 'button_hover': '#1C3047', 'button_pressed': '#0C1724',
        'byline': '#BCD0E2', 'fg': '#F0F6FC', 'field': '#091522', 'header': '#040A10',
        'muted': '#B3C4D2', 'notice': '#5A8DB4', 'panel': '#0D1927', 'panel2': '#142438',
        'select': '#315D80', 'soft': '#7E94A7', 'warn': '#D8ECFF',
    },
})

# Mutable palette imported by the existing tabs. apply_theme updates it in-place.
COLORS = dict(PALETTES[DEFAULT_THEME_KEY])

def normalize_theme(theme_name: str | None) -> str:
    if theme_name in PALETTES:
        return str(theme_name)
    if theme_name in THEME_DISPLAY_TO_INTERNAL:
        return THEME_DISPLAY_TO_INTERNAL[str(theme_name)]
    return DEFAULT_THEME_KEY

def theme_display_name(theme_name: str | None) -> str:
    key = normalize_theme(theme_name)
    return THEME_INTERNAL_TO_DISPLAY.get(key, DEFAULT_THEME)

def set_color_palette(theme_name: str | None) -> str:
    key = normalize_theme(theme_name)
    COLORS.clear()
    COLORS.update(PALETTES[key])
    return key

def apply_theme(root: tk.Misc, theme_name: str | None = None) -> ttk.Style:
    theme = set_color_palette(theme_name)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    bg = COLORS["bg"]
    panel = COLORS["panel"]
    panel2 = COLORS["panel2"]
    field = COLORS["field"]
    fg = COLORS["fg"]
    muted = COLORS["muted"]
    select = COLORS["select"]
    header = COLORS["header"]
    border = COLORS["border"]

    try:
        root.configure(bg=bg)
    except Exception:
        pass

    # Apply the theme to generic ttk containers too. Earlier builds changed the
    # header/preview art but some default ttk frames could still look like old
    # system gray. This makes Theme selection a real toolkit-wide background
    # changer, not a WOS-style per-page background tweak.
    style.configure("TFrame", background=bg)
    style.configure("Root.TFrame", background=bg)
    style.configure("Body.TFrame", background=bg)
    style.configure("ThemeBody.TFrame", background=bg)
    style.configure("Header.TFrame", background=header)
    style.configure("Card.TFrame", background=panel)
    style.configure("Panel.TFrame", background=panel)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TLabelframe", background=bg, foreground=fg, bordercolor=border)
    style.configure("TLabelframe.Label", background=bg, foreground=fg)
    style.configure("TLabelFrame", background=bg, foreground=fg, bordercolor=border)
    style.configure("TLabelFrame.Label", background=bg, foreground=fg)
    style.configure("Muted.TLabel", background=bg, foreground=muted, font=("Segoe UI", 9))
    style.configure("Warn.TLabel", background=bg, foreground=COLORS.get("warn", COLORS.get("brand", fg)), font=("Segoe UI", 10, "bold"))
    style.configure("Info.TLabel", background=bg, foreground=COLORS.get("notice", COLORS.get("muted", fg)), font=("Segoe UI", 9))
    style.configure("Byline.TLabel", background=bg, foreground=COLORS["byline"], font=("Segoe UI", 10, "bold"))
    style.configure("CardLabel.TLabel", background=panel, foreground=fg)
    style.configure("Panel.TLabel", background=panel, foreground=fg)
    style.configure("HeaderTitle.TLabel", background=header, foreground=COLORS["brand"], font=("Segoe UI", 22, "bold"))
    style.configure("Header.TLabel", background=bg, foreground=COLORS["brand"], font=("Segoe UI", 16, "bold"))
    style.configure("Brand.TLabel", background=header, foreground=COLORS["brand"], font=("Segoe UI", 18, "bold"))
    style.configure("ToolLogo.TLabel", background=bg, foreground=COLORS["brand"], font=("Segoe UI", 16, "bold"))
    style.configure("ToolHeader.TLabel", background=bg, foreground=COLORS["brand"], font=("Segoe UI", 14, "bold"))
    style.configure("Byline.TLabel", background=header, foreground=COLORS["byline"], font=("Segoe UI", 10, "bold"))
    style.configure("HeaderNote.TLabel", background=header, foreground=muted, font=("Segoe UI", 9))
    style.configure("HeaderMeta.TLabel", background=header, foreground=muted, font=("Segoe UI", 10))
    style.configure("SectionTitle.TLabel", background=bg, foreground=fg, font=("Segoe UI", 14, "bold"))
    style.configure("Status.TLabel", background=panel, foreground=muted)
    style.configure("TEntry", fieldbackground=field, foreground=fg, insertcolor=fg, bordercolor=border)
    style.map("TEntry",
        fieldbackground=[("disabled", field), ("readonly", field), ("focus", field)],
        foreground=[("disabled", muted), ("readonly", fg), ("focus", fg)],
    )
    style.configure("TCombobox",
        fieldbackground=field,
        background=field,
        foreground=fg,
        selectbackground=field,
        selectforeground=fg,
        insertcolor=fg,
        arrowcolor=fg,
        bordercolor=border,
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", field), ("disabled", field), ("focus", field)],
        background=[("readonly", field), ("disabled", field), ("active", panel2)],
        foreground=[("readonly", fg), ("disabled", muted), ("focus", fg)],
        selectbackground=[("readonly", field), ("focus", field)],
        selectforeground=[("readonly", fg), ("focus", fg)],
    )
    try:
        root.option_add("*TCombobox*Listbox.background", field)
        root.option_add("*TCombobox*Listbox.foreground", fg)
        root.option_add("*TCombobox*Listbox.selectBackground", select)
        root.option_add("*TCombobox*Listbox.selectForeground", fg)
        root.option_add("*Entry.background", field)
        root.option_add("*Entry.foreground", fg)
        root.option_add("*Entry.insertBackground", fg)
        root.option_add("*Text.background", field)
        root.option_add("*Text.foreground", fg)
        root.option_add("*Text.insertBackground", fg)
    except Exception:
        pass
    style.configure("TCheckbutton", background=bg, foreground=fg)
    style.map("TCheckbutton", background=[("active", bg)], foreground=[("active", fg)])
    style.configure("Header.TCheckbutton", background=header, foreground=fg, font=("Segoe UI", 9, "bold"))
    style.map("Header.TCheckbutton", background=[("active", header)], foreground=[("active", fg), ("disabled", muted)])
    style.configure("TButton", background=COLORS["button"], foreground=fg, padding=(10, 6), bordercolor=border)
    style.map("TButton", background=[("pressed", COLORS["button_pressed"]), ("active", COLORS["button_hover"])], foreground=[("active", fg)])
    style.configure("Accent.TButton", background=COLORS["accent"], foreground=fg, padding=(12, 6), font=("Segoe UI", 9, "bold"))
    style.map("Accent.TButton", background=[("pressed", COLORS["accent_pressed"]), ("active", COLORS["accent_hover"])], foreground=[("active", fg)])
    style.configure("Extract.TButton", background=COLORS["button"], foreground=fg, padding=(12, 6), font=("Segoe UI", 9, "bold"))
    style.map("Extract.TButton", background=[("pressed", COLORS["button_pressed"]), ("active", COLORS["button_hover"])], foreground=[("active", fg), ("pressed", fg)])
    style.configure("TNotebook", background=bg, borderwidth=0)
    style.configure("TNotebook.Client", background=bg)
    style.configure("TPanedwindow", background=bg)
    style.configure("Sash", background=COLORS["accent"])
    style.configure("TNotebook.Tab", background=panel, foreground=muted, padding=(11, 7))
    style.map("TNotebook.Tab", background=[("selected", panel2), ("active", COLORS["button"])], foreground=[("selected", fg), ("active", fg)])
    style.configure("Treeview", background=field, fieldbackground=field, foreground=fg)
    style.configure("Treeview.Heading", background=panel, foreground=fg)
    style.map("Treeview", background=[("selected", select)], foreground=[("selected", fg)])
    return style


def refresh_tk_widget_colors(widget: tk.Misc) -> None:
    """Refresh non-ttk widgets after a global theme switch."""
    bg = COLORS["bg"]
    panel = COLORS["panel"]
    field = COLORS["field"]
    fg = COLORS["fg"]
    muted = COLORS["muted"]
    select = COLORS["select"]
    for child in widget.winfo_children():
        try:
            cls = child.winfo_class()
            if cls == "Text":
                child.configure(bg=field, fg=fg, insertbackground=fg, selectbackground=select, selectforeground=fg)
            elif cls == "Listbox":
                child.configure(bg=field, fg=fg, selectbackground=select, selectforeground=fg)
            elif cls == "Canvas":
                child.configure(bg=panel, highlightbackground=panel, highlightcolor=COLORS["accent"])
            elif cls == "Button":
                child.configure(
                    bg=COLORS.get("button", panel),
                    fg=fg,
                    activebackground=COLORS.get("button_hover", panel),
                    activeforeground=fg,
                    highlightbackground=COLORS.get("border", panel),
                    highlightcolor=COLORS.get("accent", panel),
                )
            elif cls in ("Frame", "Toplevel", "Labelframe"):
                child.configure(bg=bg)
            elif cls in ("Label",):
                child.configure(bg=bg, fg=fg)
            elif cls in ("Entry",):
                child.configure(bg=field, fg=fg, insertbackground=fg, highlightbackground=COLORS.get("border", panel), highlightcolor=COLORS.get("accent", panel))
        except Exception:
            pass
        try:
            refresh_tk_widget_colors(child)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Optional FULL THEME overlay
# ---------------------------------------------------------------------------
# The normal apply_theme()/refresh_tk_widget_colors() path above is intentionally
# left unchanged.  FULL THEME is an opt-in overlay used by the main window.  It
# assigns temporary palette-driven ttk styles and direct Tk colors, then restores
# each widget's original style/options when the toggle is switched back off.


def _full_theme_walk(widget: tk.Misc):
    """Yield widget and all current descendants."""
    yield widget
    try:
        for child in widget.winfo_children():
            yield from _full_theme_walk(child)
    except Exception:
        return


def _full_theme_background_for_style(style_name: str) -> str:
    name = (style_name or "").lower()
    if "header" in name:
        return COLORS["header"]
    if any(token in name for token in ("panel", "card", "status", "rebuildcard")):
        return COLORS["panel"]
    return COLORS["bg"]


def _full_theme_foreground_for_style(style_name: str) -> str:
    name = (style_name or "").lower()
    if any(token in name for token in ("muted", "help", "meta", "note", "status", "small")):
        return COLORS["muted"]
    if any(token in name for token in ("brand", "title", "toolheader", "toollogo")):
        return COLORS.get("brand", COLORS["fg"])
    if "warn" in name:
        return COLORS.get("warn", COLORS["fg"])
    if "info" in name:
        return COLORS.get("notice", COLORS["fg"])
    if "byline" in name:
        return COLORS.get("byline", COLORS["fg"])
    return COLORS["fg"]


def _configure_full_ttk_style(style: ttk.Style, base_style: str, widget_class: str) -> str:
    """Create/update a temporary full-theme style while preserving layout/font options."""
    base_style = base_style or widget_class
    full_style = f"SM3Full.{base_style}"

    # Copy explicit options/maps from the original style so fonts, padding,
    # row heights, etc. remain unchanged while colors become palette-wide.
    try:
        base_cfg = dict(style.configure(base_style) or {})
    except Exception:
        base_cfg = {}
    try:
        base_map = dict(style.map(base_style) or {})
    except Exception:
        base_map = {}

    cls = widget_class
    bg = _full_theme_background_for_style(base_style)
    fg = _full_theme_foreground_for_style(base_style)
    field = COLORS["field"]
    panel = COLORS["panel"]
    panel2 = COLORS["panel2"]
    border = COLORS["border"]
    select = COLORS["select"]
    button = COLORS["button"]
    button_hover = COLORS["button_hover"]
    button_pressed = COLORS["button_pressed"]
    accent = COLORS["accent"]
    accent_hover = COLORS["accent_hover"]
    accent_pressed = COLORS["accent_pressed"]

    cfg = dict(base_cfg)
    style_map = dict(base_map)

    if cls in ("TFrame", "TLabelframe", "TLabelFrame"):
        cfg.update(background=bg, bordercolor=border)
    elif cls == "TLabel":
        cfg.update(background=bg, foreground=fg)
    elif cls == "TButton":
        is_accent = "accent" in base_style.lower()
        cfg.update(background=accent if is_accent else button, foreground=COLORS["fg"], bordercolor=border)
        style_map.update(
            background=[("pressed", accent_pressed if is_accent else button_pressed),
                        ("active", accent_hover if is_accent else button_hover)],
            foreground=[("disabled", COLORS["muted"]), ("active", COLORS["fg"]), ("pressed", COLORS["fg"])],
        )
    elif cls in ("TCheckbutton", "TRadiobutton"):
        cfg.update(background=bg, foreground=fg)
        style_map.update(background=[("active", bg)], foreground=[("disabled", COLORS["muted"]), ("active", fg)])
    elif cls in ("TEntry", "TSpinbox"):
        cfg.update(fieldbackground=field, foreground=COLORS["fg"], insertcolor=COLORS["fg"], bordercolor=border)
        style_map.update(
            fieldbackground=[("disabled", field), ("readonly", field), ("focus", field)],
            foreground=[("disabled", COLORS["muted"]), ("readonly", COLORS["fg"]), ("focus", COLORS["fg"])],
        )
    elif cls == "TCombobox":
        cfg.update(fieldbackground=field, background=field, foreground=COLORS["fg"],
                   selectbackground=field, selectforeground=COLORS["fg"],
                   insertcolor=COLORS["fg"], arrowcolor=COLORS["fg"], bordercolor=border)
        style_map.update(
            fieldbackground=[("readonly", field), ("disabled", field), ("focus", field)],
            background=[("readonly", field), ("disabled", field), ("active", panel2)],
            foreground=[("readonly", COLORS["fg"]), ("disabled", COLORS["muted"]), ("focus", COLORS["fg"])],
        )
    elif cls == "Treeview":
        cfg.update(background=field, fieldbackground=field, foreground=COLORS["fg"], bordercolor=border)
        style_map.update(background=[("selected", select)], foreground=[("selected", COLORS["fg"])])
    elif cls in ("TScrollbar", "Horizontal.TScrollbar", "Vertical.TScrollbar"):
        cfg.update(background=panel2, troughcolor=field, bordercolor=border, arrowcolor=COLORS["fg"])
        style_map.update(background=[("active", button_hover), ("pressed", button_pressed)])
    elif cls == "TProgressbar":
        cfg.update(background=accent, troughcolor=field, bordercolor=border)
    elif cls in ("TPanedwindow", "TSeparator"):
        cfg.update(background=bg)
    elif cls == "TScale":
        cfg.update(background=bg, troughcolor=field)

    try:
        style.configure(full_style, **cfg)
    except Exception:
        # Some Tk builds reject one or more optional style keys.  Fall back to
        # the universally supported color subset for the class.
        safe = {}
        if cls in ("TFrame", "TLabelframe", "TLabelFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TPanedwindow", "TSeparator", "TScale"):
            safe["background"] = bg
        if cls in ("TLabel", "TCheckbutton", "TRadiobutton"):
            safe["foreground"] = fg
        try:
            if safe:
                style.configure(full_style, **safe)
        except Exception:
            pass
    try:
        if style_map:
            style.map(full_style, **style_map)
    except Exception:
        pass

    # Treeview headings and Labelframe captions follow the widget style prefix.
    if cls == "Treeview":
        try:
            heading = f"{full_style}.Heading"
            base_heading = f"{base_style}.Heading" if base_style != "Treeview" else "Treeview.Heading"
            heading_cfg = dict(style.configure(base_heading) or {})
            heading_cfg.update(background=panel, foreground=COLORS["fg"], bordercolor=border)
            style.configure(heading, **heading_cfg)
        except Exception:
            pass
    elif cls in ("TLabelframe", "TLabelFrame"):
        try:
            label_style = f"{full_style}.Label"
            style.configure(label_style, background=bg, foreground=fg)
        except Exception:
            pass

    return full_style


def _capture_tk_options(widget: tk.Misc, option_names: tuple[str, ...]) -> dict[str, object]:
    saved: dict[str, object] = {}
    for option in option_names:
        try:
            if option in widget.keys():
                saved[option] = widget.cget(option)
        except Exception:
            pass
    return saved


def _apply_full_tk_widget(widget: tk.Misc) -> None:
    """Apply palette colors directly to classic Tk widgets."""
    try:
        cls = widget.winfo_class()
    except Exception:
        return
    bg = COLORS["bg"]
    panel = COLORS["panel"]
    field = COLORS["field"]
    fg = COLORS["fg"]
    muted = COLORS["muted"]
    select = COLORS["select"]
    border = COLORS["border"]
    accent = COLORS["accent"]
    button = COLORS["button"]
    button_hover = COLORS["button_hover"]

    try:
        if cls in ("Tk", "Toplevel", "Frame", "Labelframe"):
            widget.configure(bg=bg, highlightbackground=border, highlightcolor=accent)
        elif cls == "Label":
            widget.configure(bg=bg, fg=fg, highlightbackground=border)
        elif cls in ("Text", "Listbox"):
            widget.configure(bg=field, fg=fg, insertbackground=fg,
                             selectbackground=select, selectforeground=fg,
                             highlightbackground=border, highlightcolor=accent)
        elif cls in ("Entry", "Spinbox"):
            widget.configure(bg=field, fg=fg, insertbackground=fg,
                             selectbackground=select, selectforeground=fg,
                             highlightbackground=border, highlightcolor=accent)
        elif cls == "Canvas":
            widget.configure(bg=panel, highlightbackground=border, highlightcolor=accent)
        elif cls == "Button":
            widget.configure(bg=button, fg=fg, activebackground=button_hover,
                             activeforeground=fg, highlightbackground=border,
                             highlightcolor=accent)
        elif cls in ("Checkbutton", "Radiobutton"):
            widget.configure(bg=bg, fg=fg, activebackground=bg,
                             activeforeground=fg, selectcolor=field,
                             highlightbackground=border)
        elif cls == "Scale":
            widget.configure(bg=bg, fg=fg, troughcolor=field,
                             activebackground=accent, highlightbackground=border)
        elif cls == "Menu":
            widget.configure(bg=panel, fg=fg, activebackground=select,
                             activeforeground=fg, selectcolor=accent)
    except Exception:
        pass


def apply_full_theme_overrides(root: tk.Misc) -> None:
    """Opt-in whole-window theme overlay. Safe to call repeatedly on theme changes."""
    style = ttk.Style(root)
    active = bool(getattr(root, "_sm3_full_theme_active", False))

    if not active:
        root._sm3_full_theme_ttk_originals = []
        root._sm3_full_theme_tk_originals = []
        root._sm3_full_theme_active = True

    ttk_originals: list[tuple[tk.Misc, str]] = getattr(root, "_sm3_full_theme_ttk_originals", [])
    tk_originals: list[tuple[tk.Misc, dict[str, object]]] = getattr(root, "_sm3_full_theme_tk_originals", [])

    # Capture widgets that appeared after FULL THEME was enabled as well (for
    # example a dialog opened while the toggle is on). This keeps the overlay
    # fully reversible even for late-created UI.
    for widget in _full_theme_walk(root):
        try:
            if isinstance(widget, ttk.Widget) and "style" in widget.keys():
                if not any(saved_widget is widget for saved_widget, _saved_style in ttk_originals):
                    ttk_originals.append((widget, str(widget.cget("style") or "")))
                continue
        except Exception:
            pass

        if any(saved_widget is widget for saved_widget, _saved in tk_originals):
            continue
        try:
            cls = widget.winfo_class()
        except Exception:
            cls = ""
        options = {
            "Tk": ("background", "highlightbackground", "highlightcolor"),
            "Toplevel": ("background", "highlightbackground", "highlightcolor"),
            "Frame": ("background", "highlightbackground", "highlightcolor"),
            "Labelframe": ("background", "foreground", "highlightbackground", "highlightcolor"),
            "Label": ("background", "foreground", "highlightbackground"),
            "Text": ("background", "foreground", "insertbackground", "selectbackground", "selectforeground", "highlightbackground", "highlightcolor"),
            "Listbox": ("background", "foreground", "selectbackground", "selectforeground", "highlightbackground", "highlightcolor"),
            "Entry": ("background", "foreground", "insertbackground", "selectbackground", "selectforeground", "highlightbackground", "highlightcolor"),
            "Spinbox": ("background", "foreground", "insertbackground", "selectbackground", "selectforeground", "highlightbackground", "highlightcolor"),
            "Canvas": ("background", "highlightbackground", "highlightcolor"),
            "Button": ("background", "foreground", "activebackground", "activeforeground", "highlightbackground", "highlightcolor"),
            "Checkbutton": ("background", "foreground", "activebackground", "activeforeground", "selectcolor", "highlightbackground"),
            "Radiobutton": ("background", "foreground", "activebackground", "activeforeground", "selectcolor", "highlightbackground"),
            "Scale": ("background", "foreground", "troughcolor", "activebackground", "highlightbackground"),
            "Menu": ("background", "foreground", "activebackground", "activeforeground", "selectcolor"),
        }.get(cls, ())
        if options:
            saved = _capture_tk_options(widget, options)
            if saved:
                tk_originals.append((widget, saved))

    root._sm3_full_theme_ttk_originals = ttk_originals
    root._sm3_full_theme_tk_originals = tk_originals

    # Recolor all current widgets.
    for widget in _full_theme_walk(root):
        try:
            if isinstance(widget, ttk.Widget) and "style" in widget.keys():
                original = ""
                for saved_widget, saved_style in ttk_originals:
                    if saved_widget is widget:
                        original = saved_style
                        break
                base_style = original or widget.winfo_class()
                # Notebook styles determine companion .Tab styles and are already
                # covered by the normal theme path; avoid disturbing tab geometry.
                if widget.winfo_class() == "TNotebook":
                    continue
                full_style = _configure_full_ttk_style(style, base_style, widget.winfo_class())
                widget.configure(style=full_style)
                continue
        except Exception:
            pass
        _apply_full_tk_widget(widget)


def restore_full_theme_overrides(root: tk.Misc) -> None:
    """Restore styles/options captured when FULL THEME was enabled."""
    if not bool(getattr(root, "_sm3_full_theme_active", False)):
        return

    for widget, style_name in getattr(root, "_sm3_full_theme_ttk_originals", []):
        try:
            if widget.winfo_exists() and "style" in widget.keys():
                widget.configure(style=style_name)
        except Exception:
            pass

    for widget, saved in getattr(root, "_sm3_full_theme_tk_originals", []):
        try:
            if widget.winfo_exists():
                widget.configure(**saved)
        except Exception:
            pass

    root._sm3_full_theme_ttk_originals = []
    root._sm3_full_theme_tk_originals = []
    root._sm3_full_theme_active = False
