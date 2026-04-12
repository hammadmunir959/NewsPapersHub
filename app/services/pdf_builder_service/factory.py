from app.services.pdf_builder_service.dawn_builder import DawnBuilder

def get_builder(newspaper_name: str, date_str: str):
    """Factory to return the correct builder instance for a newspaper."""
    newspaper_name = newspaper_name.lower()
    
    if newspaper_name == "dawn":
        return DawnBuilder(date_str)
    
    # Placeholder for future newspapers
    # if newspaper_name == "the_news":
    #     return TheNewsBuilder(date_str)
        
    raise ValueError(f"No builder found for newspaper: {newspaper_name}")
