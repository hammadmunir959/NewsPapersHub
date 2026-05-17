import re

def normalize_jid(number: str) -> str:
    """Normalize a phone number string to a plain WhatsApp JID user part.

    Accepts formats: +923001234567, 92-300-1234567, 923001234567, 03556859840
    Returns: '923001234567', '923556859840'
    """
    # Strip all non-numeric characters (handles +, -, spaces, parentheses)
    clean = re.sub(r"\D", "", number)
    
    # If it's a local Pakistani number starting with 03 (e.g. 03556859840)
    # convert it to 92 format
    if clean.startswith("03") and len(clean) == 11:
        clean = "92" + clean[1:]
        
    return clean


def get_dynamic_greeting() -> str:
    """Return 'Good morning', 'Good afternoon', 'Good evening', or 'Hello' based on current hour."""
    from datetime import datetime
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 22:
        return "Good evening"
    else:
        return "Hello"
