"""
Konfigurierbare Farben für Aktivitätstypen
Separate Farben für Light- und Dark-Mode
"""

# Farbkonfiguration für Light-Mode (klar, aber nicht zu dominant)
LIGHT_MODE_COLORS = {
    'team': '#C6B8FF',         # Soft Indigo
    'prepractice': '#FFE0B3',  # Soft Amber
    'individual': '#BFE9D3',   # Soft Mint
    'group': '#B7D4FF'         # Soft Blue
}

# Farbkonfiguration für Dark-Mode (kräftiger, gut unterscheidbar)
DARK_MODE_COLORS = {
    'team': '#8B7BFF',         # Bright Indigo
    'prepractice': '#FB923C',  # Warm Amber
    'individual': '#34D399',   # Emerald
    'group': '#60A5FA'         # Bright Blue
}

def _get_color_from_db(activity_type, theme):
    try:
        from .models import ActivityType
        row = ActivityType.query.filter_by(key=activity_type).first()
        if not row:
            return None
        return row.dark_color if theme == 'dark' else row.light_color
    except Exception:
        return None

def get_activity_color_map(theme='light'):
    try:
        from .models import ActivityType
        rows = ActivityType.query.all()
        if not rows:
            raise RuntimeError('No activity types configured')
        if theme == 'dark':
            return {row.key: row.dark_color for row in rows}
        return {row.key: row.light_color for row in rows}
    except Exception:
        return DARK_MODE_COLORS.copy() if theme == 'dark' else LIGHT_MODE_COLORS.copy()

def get_activity_color(activity_type, theme='light'):
    """
    Gibt die Farbe für einen Aktivitätstyp zurück.
    
    Args:
        activity_type: Der Typ der Aktivität ('team', 'prepractice', 'individual', 'group')
        theme: 'light' oder 'dark'
    
    Returns:
        Hex-Farbcode als String
    """
    db_color = _get_color_from_db(activity_type, theme)
    if db_color:
        return db_color
    color_map = DARK_MODE_COLORS if theme == 'dark' else LIGHT_MODE_COLORS
    return color_map.get(activity_type, '#E8E8E8' if theme == 'light' else '#4A4A4A')

def get_all_colors(theme='light'):
    """
    Gibt alle Farben für ein Theme zurück.
    
    Args:
        theme: 'light' oder 'dark'
    
    Returns:
        Dictionary mit allen Aktivitätsfarben
    """
    return DARK_MODE_COLORS.copy() if theme == 'dark' else LIGHT_MODE_COLORS.copy()
