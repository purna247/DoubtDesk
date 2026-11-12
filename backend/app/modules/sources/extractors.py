import hashlib
import io
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import pymupdf
import docx
import pptx


@dataclass
class ExtractedChunk:
    chunk_index: int
    content_text: str
    chunk_type: str  # paragraph | heading | table | caption | other
    content_hash: str
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    section_path: Optional[str] = None
    metadata_json: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedAsset:
    asset_type: str  # image | diagram | embedded_table
    bytes_data: bytes
    sha256_checksum: str
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    surrounding_text: Optional[str] = None
    metadata_json: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    extractor_name: str
    extractor_version: str
    status: str  # succeeded | partial | failed
    chunks: List[ExtractedChunk]
    assets: List[ExtractedAsset]
    warnings: List[str]
    raw_text_checksum: str
    error_code: Optional[str] = None
    safe_error_summary: Optional[str] = None


class DocumentExtractionEngine:
    """Multi-format academic document extractor for PDF, DOCX, and PPTX."""

    EXTRACTOR_NAME = "DoubtDesk-UnifiedExtractor"
    EXTRACTOR_VERSION = "1.0.0"

    @classmethod
    def extract(cls, file_bytes: bytes, file_extension: str, filename: str) -> ExtractionResult:
        ext = file_extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"

        try:
            if ext == ".pdf":
                return cls._extract_pdf(file_bytes)
            elif ext in (".docx", ".doc"):
                return cls._extract_docx(file_bytes)
            elif ext in (".pptx", ".ppt"):
                return cls._extract_pptx(file_bytes)
            elif ext in (".txt", ".md"):
                return cls._extract_plain_text(file_bytes)
            else:
                return ExtractionResult(
                    extractor_name=cls.EXTRACTOR_NAME,
                    extractor_version=cls.EXTRACTOR_VERSION,
                    status="failed",
                    chunks=[],
                    assets=[],
                    warnings=[f"Unsupported file extension: {ext}"],
                    raw_text_checksum="",
                    error_code="UNSUPPORTED_FORMAT",
                    safe_error_summary=f"Parser not registered for extension {ext}",
                )
        except Exception:
            return ExtractionResult(
                extractor_name=cls.EXTRACTOR_NAME,
                extractor_version=cls.EXTRACTOR_VERSION,
                status="failed",
                chunks=[],
                assets=[],
                warnings=["The file could not be parsed as a valid supported document."],
                raw_text_checksum="",
                error_code="EXTRACTION_FAILURE",
                safe_error_summary="The file could not be parsed. Confirm its format and integrity, then try again.",
            )

    @classmethod
    def _extract_plain_text(cls, file_bytes: bytes) -> ExtractionResult:
        """Extract UTF-8 text and Markdown paragraphs with stable line provenance."""
        raw_text = file_bytes.decode("utf-8-sig")
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        chunks: List[ExtractedChunk] = []
        current_lines: List[str] = []
        start_line = 1
        for line_number, line in enumerate(raw_text.splitlines(), start=1):
            if line.strip():
                if not current_lines:
                    start_line = line_number
                current_lines.append(line.strip())
            elif current_lines:
                content = "\n".join(current_lines).strip()
                chunks.append(ExtractedChunk(
                    chunk_index=len(chunks),
                    content_text=content,
                    chunk_type="paragraph",
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    metadata_json={"line_start": start_line, "line_end": line_number - 1},
                ))
                current_lines = []
        if current_lines:
            content = "\n".join(current_lines).strip()
            chunks.append(ExtractedChunk(
                chunk_index=len(chunks),
                content_text=content,
                chunk_type="paragraph",
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                metadata_json={"line_start": start_line, "line_end": len(raw_text.splitlines())},
            ))
        if not chunks:
            return ExtractionResult(
                extractor_name=cls.EXTRACTOR_NAME, extractor_version=cls.EXTRACTOR_VERSION,
                status="failed", chunks=[], assets=[], warnings=["Document contains no readable text."],
                raw_text_checksum=checksum, error_code="EMPTY_DOCUMENT",
                safe_error_summary="Document contains no readable text.",
            )
        return ExtractionResult(
            extractor_name=cls.EXTRACTOR_NAME, extractor_version=cls.EXTRACTOR_VERSION,
            status="succeeded", chunks=chunks, assets=[], warnings=[], raw_text_checksum=checksum,
        )

    @classmethod
    def _extract_pdf(cls, file_bytes: bytes) -> ExtractionResult:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        chunks: List[ExtractedChunk] = []
        assets: List[ExtractedAsset] = []
        warnings: List[str] = []
        total_text = ""
        chunk_idx = 0

        if len(doc) == 0:
            return ExtractionResult(
                extractor_name=cls.EXTRACTOR_NAME,
                extractor_version=cls.EXTRACTOR_VERSION,
                status="failed",
                chunks=[],
                assets=[],
                warnings=["PDF document contains 0 pages."],
                raw_text_checksum="",
                error_code="EMPTY_DOCUMENT",
                safe_error_summary="PDF document has no readable pages.",
            )

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1

            # Extract tables if detectable
            try:
                tables = page.find_tables()
                for table in tables:
                    table_data = table.extract()
                    if table_data:
                        # Format as markdown-like table text
                        table_lines = [" | ".join(str(cell or "").strip() for cell in row) for row in table_data]
                        table_str = "\n".join(table_lines)
                        if table_str.strip():
                            h = hashlib.sha256(table_str.encode("utf-8")).hexdigest()
                            chunks.append(
                                ExtractedChunk(
                                    chunk_index=chunk_idx,
                                    page_number=page_num,
                                    chunk_type="table",
                                    content_text=table_str,
                                    content_hash=h,
                                    metadata_json={"rows": len(table_data)},
                                )
                            )
                            chunk_idx += 1
                            total_text += "\n" + table_str
            except Exception as e:
                warnings.append(f"Page {page_num} table extraction warning: {str(e)[:100]}")

            # Extract text blocks
            blocks = page.get_text("blocks")
            for b in blocks:
                # b = (x0, y0, x1, y1, text, block_no, block_type)
                # block_type 0 = text, 1 = image
                if len(b) >= 7 and b[6] == 0:
                    text_content = b[4].strip()
                    if not text_content:
                        continue

                    # Heuristic for headings vs paragraph based on length / uppercase
                    chunk_type = "heading" if len(text_content) < 80 and ("\n" not in text_content or text_content.isupper()) else "paragraph"
                    h = hashlib.sha256(text_content.encode("utf-8")).hexdigest()

                    chunks.append(
                        ExtractedChunk(
                            chunk_index=chunk_idx,
                            page_number=page_num,
                            chunk_type=chunk_type,
                            content_text=text_content,
                            content_hash=h,
                            metadata_json={"bbox": list(b[:4])},
                        )
                    )
                    chunk_idx += 1
                    total_text += "\n" + text_content

            # Extract embedded images
            image_list = page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                base_img = doc.extract_image(xref)
                if base_img:
                    img_bytes = base_img["image"]
                    img_hash = hashlib.sha256(img_bytes).hexdigest()
                    assets.append(
                        ExtractedAsset(
                            asset_type="image",
                            bytes_data=img_bytes,
                            sha256_checksum=img_hash,
                            page_number=page_num,
                            metadata_json={"format": base_img["ext"], "width": base_img["width"], "height": base_img["height"]},
                        )
                    )

        doc.close()

        total_text = total_text.strip()
        raw_checksum = hashlib.sha256(total_text.encode("utf-8")).hexdigest() if total_text else ""

        if not total_text:
            warnings.append("No text could be extracted from PDF (possible scanned raster images without OCR).")
            return ExtractionResult(
                extractor_name=cls.EXTRACTOR_NAME,
                extractor_version=cls.EXTRACTOR_VERSION,
                status="partial" if assets else "failed",
                chunks=chunks,
                assets=assets,
                warnings=warnings,
                raw_text_checksum=raw_checksum,
                error_code="EMPTY_TEXT" if not assets else None,
                safe_error_summary="Document extracted with warnings: No selectable text found." if assets else "No selectable text found in PDF.",
            )

        status = "partial" if warnings else "succeeded"
        return ExtractionResult(
            extractor_name=cls.EXTRACTOR_NAME,
            extractor_version=cls.EXTRACTOR_VERSION,
            status=status,
            chunks=chunks,
            assets=assets,
            warnings=warnings,
            raw_text_checksum=raw_checksum,
        )

    @classmethod
    def _extract_docx(cls, file_bytes: bytes) -> ExtractionResult:
        doc = docx.Document(io.BytesIO(file_bytes))
        chunks: List[ExtractedChunk] = []
        assets: List[ExtractedAsset] = []
        warnings: List[str] = []
        total_text = ""
        chunk_idx = 0
        current_section = ""

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            style_name = p.style.name.lower() if p.style else ""
            if "heading" in style_name:
                current_section = text
                chunk_type = "heading"
            else:
                chunk_type = "paragraph"

            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunks.append(
                ExtractedChunk(
                    chunk_index=chunk_idx,
                    chunk_type=chunk_type,
                    section_path=current_section or None,
                    content_text=text,
                    content_hash=h,
                    metadata_json={"style": p.style.name if p.style else None},
                )
            )
            chunk_idx += 1
            total_text += "\n" + text

        # Extract tables
        for t_idx, table in enumerate(doc.tables):
            table_lines = []
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells]
                table_lines.append(" | ".join(row_cells))
            t_str = "\n".join(table_lines)
            if t_str.strip():
                h = hashlib.sha256(t_str.encode("utf-8")).hexdigest()
                chunks.append(
                    ExtractedChunk(
                        chunk_index=chunk_idx,
                        chunk_type="table",
                        section_path=current_section or None,
                        content_text=t_str,
                        content_hash=h,
                        metadata_json={"table_index": t_idx, "rows": len(table.rows)},
                    )
                )
                chunk_idx += 1
                total_text += "\n" + t_str

        total_text = total_text.strip()
        raw_checksum = hashlib.sha256(total_text.encode("utf-8")).hexdigest() if total_text else ""

        if not total_text:
            warnings.append("Document contains no readable paragraphs or tables.")
            return ExtractionResult(
                extractor_name=cls.EXTRACTOR_NAME,
                extractor_version=cls.EXTRACTOR_VERSION,
                status="failed",
                chunks=[],
                assets=[],
                warnings=warnings,
                raw_text_checksum="",
                error_code="EMPTY_DOCX",
                safe_error_summary="DOCX file contains no text.",
            )

        return ExtractionResult(
            extractor_name=cls.EXTRACTOR_NAME,
            extractor_version=cls.EXTRACTOR_VERSION,
            status="succeeded",
            chunks=chunks,
            assets=assets,
            warnings=warnings,
            raw_text_checksum=raw_checksum,
        )

    @classmethod
    def _extract_pptx(cls, file_bytes: bytes) -> ExtractionResult:
        prs = pptx.Presentation(io.BytesIO(file_bytes))
        chunks: List[ExtractedChunk] = []
        assets: List[ExtractedAsset] = []
        warnings: List[str] = []
        total_text = ""
        chunk_idx = 0

        for slide_idx, slide in enumerate(prs.slides):
            slide_num = slide_idx + 1
            slide_title = ""

            # Check if slide has title shape
            if slide.shapes.title and slide.shapes.title.text.strip():
                slide_title = slide.shapes.title.text.strip()
                h = hashlib.sha256(slide_title.encode("utf-8")).hexdigest()
                chunks.append(
                    ExtractedChunk(
                        chunk_index=chunk_idx,
                        slide_number=slide_num,
                        section_path=slide_title,
                        chunk_type="heading",
                        content_text=slide_title,
                        content_hash=h,
                    )
                )
                chunk_idx += 1
                total_text += "\n" + slide_title

            for shape in slide.shapes:
                if shape == slide.shapes.title:
                    continue

                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
                            chunks.append(
                                ExtractedChunk(
                                    chunk_index=chunk_idx,
                                    slide_number=slide_num,
                                    section_path=slide_title or None,
                                    chunk_type="paragraph",
                                    content_text=text,
                                    content_hash=h,
                                )
                            )
                            chunk_idx += 1
                            total_text += "\n" + text

                elif shape.has_table:
                    table = shape.table
                    table_lines = []
                    for row in table.rows:
                        row_cells = [cell.text.strip() for cell in row.cells]
                        table_lines.append(" | ".join(row_cells))
                    t_str = "\n".join(table_lines)
                    if t_str.strip():
                        h = hashlib.sha256(t_str.encode("utf-8")).hexdigest()
                        chunks.append(
                            ExtractedChunk(
                                chunk_index=chunk_idx,
                                slide_number=slide_num,
                                section_path=slide_title or None,
                                chunk_type="table",
                                content_text=t_str,
                                content_hash=h,
                            )
                        )
                        chunk_idx += 1
                        total_text += "\n" + t_str

        total_text = total_text.strip()
        raw_checksum = hashlib.sha256(total_text.encode("utf-8")).hexdigest() if total_text else ""

        if not total_text:
            warnings.append("Presentation contains no readable text.")
            return ExtractionResult(
                extractor_name=cls.EXTRACTOR_NAME,
                extractor_version=cls.EXTRACTOR_VERSION,
                status="failed",
                chunks=[],
                assets=[],
                warnings=warnings,
                raw_text_checksum="",
                error_code="EMPTY_PPTX",
                safe_error_summary="PPTX presentation has no extractable text.",
            )

        return ExtractionResult(
            extractor_name=cls.EXTRACTOR_NAME,
            extractor_version=cls.EXTRACTOR_VERSION,
            status="succeeded",
            chunks=chunks,
            assets=assets,
            warnings=warnings,
            raw_text_checksum=raw_checksum,
        )
