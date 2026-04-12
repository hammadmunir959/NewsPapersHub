import img2pdf
import logging
import os
from PIL import Image

logger = logging.getLogger(__name__)


class PDFBuilder:
    """Service to handle PDF creation from different source types (images, HTML)."""

    @staticmethod
    async def build(method: str, source_data: list[str] | str, output_path: str) -> str:
        """Dispatch to the correct PDF building method.

        Args:
            method: 'epaper' (images) or 'text' (HTML).
            source_data: List of image paths or raw HTML content.
            output_path: Destination path for the PDF file.
        """
        if method == "epaper":
            return PDFBuilder.build_pdf_from_images(source_data, output_path)
        elif method == "text":
            return await PDFBuilder.build_pdf_from_html(source_data, output_path)
        else:
            raise ValueError(f"Unsupported PDF building method: {method}")

    @staticmethod
    def build_pdf_from_images(image_paths: list[str], output_path: str) -> str:
        """Assemble a list of images into a single PDF (lossless)."""
        valid_paths: list[str] = []

        for path in image_paths:
            try:
                with Image.open(path) as img:
                    img.verify()
                valid_paths.append(path)
            except Exception as e:
                logger.warning(f"Skipping invalid image {path}: {e}")

        if not valid_paths:
            raise ValueError("No valid images to build PDF from")

        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(valid_paths))

        logger.info(f"PDF built from images: {output_path} ({len(valid_paths)} pages)")
        return output_path
