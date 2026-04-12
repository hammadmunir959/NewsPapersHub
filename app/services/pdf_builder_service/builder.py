from app.services.pdf_builder_service.factory import get_builder

class ReportLabBuilder:
    """Main entry point for building newspaper PDFs using the factory pattern."""

    @staticmethod
    def build_newspaper_pdf(sections_data: list[dict], output_path: str,
                            newspaper: str, date_str: str) -> str:
        # 1. Get the specialized builder for the newspaper
        builder = get_builder(newspaper, date_str)
        
        # 2. Execute the build process
        return builder.build(sections_data, output_path)
