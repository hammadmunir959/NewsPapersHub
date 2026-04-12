import os
import shutil
from datetime import datetime, timezone, date

from app.core.config import get_newspaper_dir, get_pdf_path, SUPPORTED_NEWSPAPERS
from app.services.scraper_service import Scraper
from app.services.pdf_service import PDFBuilder
from app.models.schemas import PaperSuccessResponse


class NewspaperService:
    """Orchestration service to handle newspaper processing flow."""

    @staticmethod
    def validate_date(date_str: str) -> None:
        """Validate date format and business rules."""
        try:
            parsed = date.fromisoformat(date_str)
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")

        if parsed > date.today():
            raise ValueError("Date must not be in the future")
        if (date.today() - parsed).days > 30:
            raise ValueError("Date must be within the last 30 days")

    @staticmethod
    async def process(newspaper: str, date_str: str, method: str = "epaper") -> PaperSuccessResponse:
        """Process a newspaper request: check cache, scrape, build PDF, return metadata."""
        # Ensure we are working with string values (if passed as Enums from the API layer)
        newspaper = str(newspaper.value) if hasattr(newspaper, "value") else str(newspaper)
        method = str(method.value) if hasattr(method, "value") else str(method)

        if newspaper not in SUPPORTED_NEWSPAPERS:
            raise ValueError(f"Unsupported newspaper: {newspaper}")

        pdf_path = get_pdf_path(newspaper, date_str, method)

        # 1. Check if PDF already exists (Cache Hit)
        if os.path.exists(pdf_path):
            size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
            return PaperSuccessResponse(
                status="success",
                message="PDF already exists. Returned from cache.",
                newspaper=newspaper,
                date=date_str,
                file_name=os.path.basename(pdf_path),
                saved_at=pdf_path,
                pages=0,  # 0 indicates cached
                size_mb=round(size_mb, 2),
            )

        # 2. Ensure output directory exists
        os.makedirs(get_newspaper_dir(newspaper), exist_ok=True)

        # 3. Scrape source data (images or HTML file)
        data_paths = await Scraper.scrape(newspaper, date_str, method)
        if not data_paths:
            raise ValueError(f"No content found for {newspaper} on {date_str} using {method}")

        # 4. Build PDF
        try:
            if method == "epaper":
                # Approach 1: Images to PDF
                await PDFBuilder.build(method, data_paths, pdf_path)
            elif method == "text":
                import json
                from app.services.pdf_builder_service import ReportLabBuilder
                
                json_file = data_paths[0]
                with open(json_file, "r", encoding="utf-8") as f:
                    sections_data = json.load(f)
                    
                ReportLabBuilder.build_newspaper_pdf(sections_data, pdf_path, newspaper, date_str)
        finally:
            # Clean up temporary files/dirs
            if data_paths:
                tmp_dir = os.path.dirname(data_paths[0])
                shutil.rmtree(tmp_dir, ignore_errors=True)

        # 5. Build response metadata
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        return PaperSuccessResponse(
            status="success",
            message="Successfully scraped and generated PDF.",
            newspaper=newspaper,
            date=date_str,
            file_name=os.path.basename(pdf_path),
            saved_at=pdf_path,
            pages=len(data_paths) if method == "epaper" else 1,
            size_mb=round(size_mb, 2),
        )
