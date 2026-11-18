import base64
import concurrent.futures
import hashlib
import io
import logging
import re
import time
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field

import httpx
import pymupdf
import docx
from docx.text.paragraph import Paragraph
from docx.table import Table
import pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedChunk:
    chunk_index: int
    content_text: str
    chunk_type: str  # paragraph | heading | table | caption | slide | question | curriculum | other
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
    """Multi-format academic document extractor for PDF, DOCX, and PPTX with structure-aware chunking."""

    EXTRACTOR_NAME = "DoubtDesk-UnifiedExtractor"
    EXTRACTOR_VERSION = "2.0.0"

    @classmethod
    def extract(cls, file_bytes: bytes, file_extension: str, filename: str) -> ExtractionResult:
        ext = file_extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"

        try:
            if ext == ".pdf":
                return cls._extract_pdf(file_bytes, filename=filename)
            elif ext in (".docx", ".doc"):
                return cls._extract_docx(file_bytes, filename=filename)
            elif ext in (".pptx", ".ppt"):
                return cls._extract_pptx(file_bytes, filename=filename)
            elif ext in (".txt", ".md"):
                return cls._extract_plain_text(file_bytes, filename=filename)
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
        except Exception as exc:
            logger.error("Document extraction error for %s: %s", filename, exc, exc_info=True)
            return ExtractionResult(
                extractor_name=cls.EXTRACTOR_NAME,
                extractor_version=cls.EXTRACTOR_VERSION,
                status="failed",
                chunks=[],
                assets=[],
                warnings=[f"Extraction failed: {str(exc)[:200]}"],
                raw_text_checksum="",
                error_code="EXTRACTION_FAILURE",
                safe_error_summary="The file could not be parsed. Confirm its format and integrity, then try again.",
            )

    @classmethod
    def _extract_plain_text(cls, file_bytes: bytes, filename: str = "") -> ExtractionResult:
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
    def _extract_pdf(cls, file_bytes: bytes, filename: str = "") -> ExtractionResult:
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

            # 1. Extract tables and record bounding boxes to prevent duplicate block extraction
            table_bboxes = []
            try:
                tables = page.find_tables()
                for table in tables:
                    table_data = table.extract()
                    if table_data:
                        table_bboxes.append(table.bbox)
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

            # 2. Extract text blocks (skip text falling inside extracted table bboxes)
            blocks = page.get_text("blocks")
            for b in blocks:
                if len(b) >= 7 and b[6] == 0:
                    text_content = b[4].strip()
                    if not text_content:
                        continue

                    # Check if block is inside any extracted table bbox
                    block_bbox = pymupdf.Rect(b[:4])
                    inside_table = False
                    for tb in table_bboxes:
                        t_rect = pymupdf.Rect(tb)
                        if t_rect.contains(block_bbox) or t_rect.intersects(block_bbox):
                            # Overlap > 60%
                            intersect_area = (t_rect & block_bbox).get_area()
                            if intersect_area > 0.6 * block_bbox.get_area():
                                inside_table = True
                                break
                    if inside_table:
                        continue

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

            # 3. Extract embedded images
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
    def _extract_docx(cls, file_bytes: bytes, filename: str = "") -> ExtractionResult:
        """
        Structure-aware DOCX extraction.
        - Preserves document reading order by iterating doc.element.body elements (paragraphs and tables interleaved).
        - Tracks hierarchical section context (Document Title > Module > Section > Subsection).
        - Deduplicates merged cells in tables (eliminating repeated module text).
        - Specializes parsing for Syllabus structures (Modules, Hours, Subtopics) and Question Banks (Questions, Marks, Sections).
        """
        doc = docx.Document(io.BytesIO(file_bytes))
        chunks: List[ExtractedChunk] = []
        assets: List[ExtractedAsset] = []
        warnings: List[str] = []
        total_text = ""
        chunk_idx = 0

        # State tracking for heading hierarchy
        current_module: Optional[str] = None
        current_section: str = "Overview"
        in_question_bank = "question" in filename.lower()
        question_counter = 1
        current_marks: Optional[int] = None

        def add_chunk(
            text: str,
            c_type: str,
            sec_path: Optional[str],
            meta: Optional[Dict[str, Any]] = None,
        ):
            nonlocal chunk_idx, total_text
            clean = text.strip()
            if not clean:
                return
            h = hashlib.sha256(clean.encode("utf-8")).hexdigest()
            chunks.append(
                ExtractedChunk(
                    chunk_index=chunk_idx,
                    content_text=clean,
                    chunk_type=c_type,
                    content_hash=h,
                    section_path=sec_path,
                    metadata_json=meta or {},
                )
            )
            chunk_idx += 1
            total_text += "\n" + clean

        for elem in doc.element.body:
            # A. Paragraph Element
            if elem.tag.endswith("p"):
                p = Paragraph(elem, doc)
                text = p.text.strip()
                if not text:
                    continue

                style_name = (p.style.name or "").lower() if p.style else ""

                # 1. Module Boundary Detection (e.g. "MODULE–I: Introduction to BCI...")
                mod_match = re.search(r"MODULE[\s\u2013-]+([I|V|X\d]+)[:\s]*(.*)", text, re.IGNORECASE)
                if mod_match:
                    current_module = f"Module {mod_match.group(1).upper()}"
                    mod_title = mod_match.group(2).strip()
                    current_section = f"{current_module}: {mod_title}" if mod_title else current_module
                    question_counter = 1
                    current_marks = None
                    add_chunk(text, "heading", current_section, {"is_module_header": True, "module": current_module})
                    continue

                # 2. Section / Examination Marks Detection (e.g. "Very Short Answer Questions — 2 Marks")
                marks_match = re.search(r"(.*?)(?:—|-|–)\s*(\d+)\s*Marks", text, re.IGNORECASE)
                if marks_match:
                    sec_name = marks_match.group(1).strip()
                    current_marks = int(marks_match.group(2))
                    in_question_bank = True
                    question_counter = 1
                    if current_module:
                        current_section = f"{current_module} > {sec_name} ({current_marks} Marks)"
                    else:
                        current_section = f"{sec_name} ({current_marks} Marks)"
                    add_chunk(text, "heading", current_section, {"marks": current_marks, "module": current_module})
                    continue

                # 3. Standard Heading Detection (Course Outcomes, Detailed Syllabus, Text Books, References Books)
                is_heading = (
                    "heading" in style_name
                    or text.endswith(":")
                    or (len(text) < 45 and (text.isupper() or style_name in ("title", "subtitle", "no spacing")))
                )

                if is_heading:
                    clean_heading = text.rstrip(":")
                    # Clear stale module context if a document-level section begins
                    if any(term in clean_heading.lower() for term in ("course outcomes", "detailed syllabus", "text books", "references books", "co-po mapping", "prerequisites")):
                        current_section = clean_heading
                        current_module = None
                    elif current_module:
                        current_section = f"{current_module} > {clean_heading}"
                    else:
                        current_section = clean_heading

                    add_chunk(text, "heading", current_section, {"heading_level": style_name})
                    continue

                # 4. Question Bank Questions
                if in_question_bank and current_marks is not None:
                    # Treat each question as an individual, structured assessment chunk
                    q_sec = f"{current_section} > Q{question_counter}"
                    add_chunk(
                        text,
                        "question",
                        q_sec,
                        {
                            "is_assessment": True,
                            "marks": current_marks,
                            "module": current_module,
                            "question_number": question_counter,
                        },
                    )
                    question_counter += 1
                    continue

                # 5. Normal Body Paragraph (e.g. Text books items, prerequisites, or body notes)
                # If bibliography or list items, preserve them under current section
                add_chunk(text, "paragraph", current_section, {"module": current_module})

            # B. Table Element
            elif elem.tag.endswith("tbl"):
                tbl = Table(elem, doc)
                if not tbl.rows:
                    continue

                # Inspect if this table is the Detailed Syllabus Table (Module I, II, III, IV)
                is_syllabus_table = False
                for r in tbl.rows[:3]:
                    for c in r.cells:
                        if re.search(r"Module[\s\u2013-]+[I|V|X\d]+", c.text, re.I):
                            is_syllabus_table = True
                            break
                    if is_syllabus_table:
                        break

                if is_syllabus_table:
                    # Specialized Syllabus Chunking: Module -> Topics -> Subtopics
                    cls._parse_syllabus_table(tbl, add_chunk)
                else:
                    # Generic / Course Outcomes / CO-PO / Prerequisites Table
                    cls._parse_generic_table(tbl, current_section, add_chunk)

        total_text = total_text.strip()
        raw_checksum = hashlib.sha256(total_text.encode("utf-8")).hexdigest() if total_text else ""

        if not total_text or not chunks:
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
                safe_error_summary="DOCX file contains no readable text.",
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
    def _parse_syllabus_table(cls, table: Table, add_chunk_fn):
        """Parse structured syllabus table into distinct, bounded chunks per module and topic."""
        r_idx = 0
        while r_idx < len(table.rows):
            row = table.rows[r_idx]
            # Deduplicate horizontally merged cells by tracking seen XML cell elements
            seen_tc = set()
            row_cells = []
            for cell in row.cells:
                if cell._tc not in seen_tc:
                    seen_tc.add(cell._tc)
                    t = cell.text.strip().replace("\n", " ")
                    if t:
                        row_cells.append(t)

            if row_cells and re.match(r"Module[\s\u2013-]*([I|V|X\d]+)", row_cells[0], re.I):
                mod_match = re.match(r"Module[\s\u2013-]*([I|V|X\d]+)", row_cells[0], re.I)
                mod_roman = mod_match.group(1).upper()
                mod_label = f"Module {mod_roman}"
                hours_label = row_cells[1] if len(row_cells) > 1 else ""

                # Next row contains the detailed syllabus topics
                if r_idx + 1 < len(table.rows):
                    content_row = table.rows[r_idx + 1]
                    seen_content_tc = set()
                    content_cells = []
                    for cell in content_row.cells:
                        if cell._tc not in seen_content_tc:
                            seen_content_tc.add(cell._tc)
                            t = cell.text.strip()
                            if t:
                                content_cells.append(t)
                    content_text = " ".join(content_cells)

                    # Split topics into focused subchunks (~400-800 chars) preserving complete topic boundaries
                    # E.g. "Introduction to BCI: ...", "EEG Brain Activation: ...", "Feature Extraction Methods: ...", "Machine Learning methods: ..."
                    subtopic_splits = re.split(
                        r"(?=(?:Introduction to BCI:|EEG Brain Activation:|Feature Extraction Methods:|Machine Learning methods for BCI|Applications of BCI:|Case Studies|BCI Hardware and Software:))",
                        content_text,
                    )

                    clean_subtopics = [st.strip() for st in subtopic_splits if st.strip()]
                    if clean_subtopics:
                        for st in clean_subtopics:
                            # Extract subtopic title before colon
                            colon_idx = st.find(":")
                            sub_title = st[:colon_idx].strip() if colon_idx != -1 and colon_idx < 50 else "Topics"
                            sub_path = f"Detailed Syllabus > {mod_label} > {sub_title}"
                            chunk_body = f"{mod_label} {hours_label}\n{st}".strip()
                            add_chunk_fn(
                                chunk_body,
                                "curriculum",
                                sub_path,
                                {"module": mod_label, "hours": hours_label, "is_syllabus": True},
                            )
                    else:
                        sub_path = f"Detailed Syllabus > {mod_label}"
                        chunk_body = f"{mod_label} {hours_label}\n{content_text}".strip()
                        add_chunk_fn(
                            chunk_body,
                            "curriculum",
                            sub_path,
                            {"module": mod_label, "hours": hours_label, "is_syllabus": True},
                        )
                    r_idx += 2
                    continue
            r_idx += 1

    @classmethod
    def _parse_generic_table(cls, table: Table, current_section: str, add_chunk_fn):
        """Parse tables with merged-cell deduplication and bounded chunking."""
        is_co_table = "course outcome" in current_section.lower()
        rows_data = []

        for row in table.rows:
            seen_tc = set()
            row_cells = []
            for cell in row.cells:
                if cell._tc not in seen_tc:
                    seen_tc.add(cell._tc)
                    t = cell.text.strip().replace("\n", " ")
                    if t:
                        row_cells.append(t)
            if row_cells:
                rows_data.append(row_cells)

        if not rows_data:
            return

        # If Course Outcomes table (e.g. CO1 | Explain...), extract each outcome cleanly
        if (is_co_table and "mapping" not in current_section.lower()) or (
            any(r[0].startswith("CO") for r in rows_data)
            and any(len(r[1]) > 25 for r in rows_data if len(r) > 1)
            and not any("PO" in r[0] for r in rows_data)
        ):
            for r in rows_data:
                co_label = r[0]
                co_desc = r[1] if len(r) > 1 else ""
                co_text = f"{co_label}: {co_desc}" if co_desc else co_label
                add_chunk_fn(
                    co_text,
                    "curriculum",
                    "Course Outcomes",
                    {"outcome_code": co_label, "is_course_outcome": True},
                )
            return

        # General table: Format as Markdown table
        header = rows_data[0]
        markdown_lines = [" | ".join(header), " | ".join(["---"] * len(header))]
        for r in rows_data[1:]:
            markdown_lines.append(" | ".join(r))
        table_str = "\n".join(markdown_lines)

        add_chunk_fn(
            table_str,
            "table",
            current_section,
            {"rows": len(rows_data), "cols": len(header)},
        )

    @classmethod
    def _extract_pptx(cls, file_bytes: bytes, filename: str = "") -> ExtractionResult:
        """
        Structure-aware PPTX extraction.
        - Preserves slide numbers, slide titles, and presentation structure.
        - Groups slide content into coherent ~500-1000 char chunks rather than fragmenting each bullet.
        - Recovers educational diagram text and visual slide content using Gemini vision when text is sparse.
        """
        prs = pptx.Presentation(io.BytesIO(file_bytes))
        chunks: List[ExtractedChunk] = []
        assets: List[ExtractedAsset] = []
        warnings: List[str] = []
        total_text = ""
        chunk_idx = 0

        clean_filename = re.sub(r"\.(pptx|ppt)$", "", filename, flags=re.I)
        settings = get_settings()
        total_slides = len(prs.slides)
        t_parse_start = time.time()
        logger.info("[PPTX Parser] Starting extraction of '%s' (%d slides total)...", filename, total_slides)

        parsed_slides = []
        visual_ocr_tasks = []

        for slide_idx, slide in enumerate(prs.slides):
            slide_num = slide_idx + 1

            # 1. Slide Title Identification
            slide_title = ""
            if slide.shapes.title and slide.shapes.title.text.strip():
                slide_title = slide.shapes.title.text.strip()
            else:
                # Look for highest text shape
                candidate_titles = []
                for sh in slide.shapes:
                    if sh.has_text_frame and sh.text_frame.text.strip():
                        candidate_titles.append((sh.top, sh.text_frame.text.strip().split("\n")[0]))
                if candidate_titles:
                    candidate_titles.sort(key=lambda x: x[0])
                    top_text = candidate_titles[0][1]
                    if len(top_text) < 70:
                        slide_title = top_text

            section_path = slide_title if slide_title else f"Slide {slide_num}"

            # 2. Extract editable slide text and tables
            body_parts: List[str] = []
            image_b64: Optional[str] = None

            for shape in slide.shapes:
                if shape == slide.shapes.title:
                    continue

                if shape.has_text_frame:
                    t = shape.text_frame.text.strip()
                    if t and t != slide_title:
                        body_parts.append(t)

                elif shape.has_table:
                    tbl = shape.table
                    tbl_lines = []
                    for row in tbl.rows:
                        row_cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                        tbl_lines.append(" | ".join(row_cells))
                    if tbl_lines:
                        body_parts.append("\n".join(tbl_lines))

                elif getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.PICTURE and hasattr(shape, "image"):
                    try:
                        img = shape.image
                        img_bytes = img.blob
                        img_hash = hashlib.sha256(img_bytes).hexdigest()
                        assets.append(
                            ExtractedAsset(
                                asset_type="image",
                                bytes_data=img_bytes,
                                sha256_checksum=img_hash,
                                slide_number=slide_num,
                                surrounding_text=slide_title or None,
                                metadata_json={"format": img.ext, "filename": getattr(img, "filename", None)},
                            )
                        )
                        if image_b64 is None and len(img_bytes) > 25000:
                            try:
                                pil_img = Image.open(io.BytesIO(img_bytes))
                                pil_img.thumbnail((800, 800))
                                buf = io.BytesIO()
                                pil_img.save(buf, format="JPEG", quality=85)
                                image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                            except Exception:
                                pass
                    except Exception:
                        pass

            # 3. Check if vision-based diagram extraction is needed
            total_editable_len = sum(len(p) for p in body_parts)
            if total_editable_len < 60 and settings.GEMINI_API_KEY and image_b64:
                visual_ocr_tasks.append((slide_idx, slide_num, slide_title, image_b64))

            # 4. Extract Speaker Notes if present
            notes_text = ""
            if getattr(slide, "has_notes_slide", False) and slide.notes_slide:
                try:
                    notes_tf = slide.notes_slide.notes_text_frame
                    if notes_tf and notes_tf.text.strip():
                        notes_text = notes_tf.text.strip()
                except Exception:
                    pass

            parsed_slides.append({
                "slide_idx": slide_idx,
                "slide_num": slide_num,
                "slide_title": slide_title,
                "section_path": section_path,
                "body_parts": body_parts,
                "notes_text": notes_text,
            })

        # Concurrent Gemini Vision OCR for diagram slides
        visual_results: Dict[int, str] = {}
        if visual_ocr_tasks:
            workers_count = min(4, len(visual_ocr_tasks))
            logger.info(
                "[Vision OCR] Parallelizing %d diagram slide extractions across %d workers via Gemini 3.5 Flash Lite...",
                len(visual_ocr_tasks),
                workers_count,
            )

            def _ocr_worker(task_item):
                s_idx, s_num, s_title, b64_str = task_item
                t_ocr = time.time()
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={settings.GEMINI_API_KEY}"
                    payload = {
                        "contents": [{
                            "parts": [
                                {"text": "Extract all readable text, titles, headings, and diagram architecture descriptions from this academic lecture slide. Be thorough and concise."},
                                {"inline_data": {"mime_type": "image/jpeg", "data": b64_str}}
                            ]
                        }]
                    }
                    with httpx.Client(timeout=16.0) as client:
                        resp = client.post(url, json=payload)
                        if resp.status_code == 200:
                            cand = resp.json().get("candidates", [])
                            if cand:
                                p_text = cand[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                                logger.info(
                                    "[Vision OCR] Slide %d/%d ('%s') diagram text extracted in %.1fs (%d chars)",
                                    s_num, total_slides, s_title, time.time() - t_ocr, len(p_text)
                                )
                                return s_idx, p_text
                except Exception as exc:
                    logger.warning("[Vision OCR] Slide %d diagram OCR failed: %s", s_num, exc)
                return s_idx, ""

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers_count) as executor:
                for s_idx, text_out in executor.map(_ocr_worker, visual_ocr_tasks):
                    if text_out:
                        visual_results[s_idx] = text_out

        logger.info(
            "[PPTX Parser] Slide structure & visual extraction completed in %.1fs (%d diagram slides processed).",
            time.time() - t_parse_start,
            len(visual_results),
        )

        for p_slide in parsed_slides:
            slide_idx = p_slide["slide_idx"]
            slide_num = p_slide["slide_num"]
            slide_title = p_slide["slide_title"]
            section_path = p_slide["section_path"]
            body_parts = p_slide["body_parts"]
            notes_text = p_slide["notes_text"]
            recovered_visual_text = visual_results.get(slide_idx, "")
            has_visual_extraction = bool(recovered_visual_text)

            # 5. Build coherent slide content
            slide_header = f"Slide {slide_num}: {slide_title}" if slide_title else f"Slide {slide_num}"
            content_blocks = [slide_header]
            if body_parts:
                content_blocks.extend(body_parts)
            if recovered_visual_text:
                content_blocks.append(f"[Visual / Diagram Content]:\n{recovered_visual_text}")
            if notes_text:
                content_blocks.append(f"[Speaker Notes]: {notes_text}")

            full_slide_content = "\n\n".join(content_blocks).strip()
            if not full_slide_content or full_slide_content == slide_header:
                continue

            # Bounded chunking: If slide content exceeds 1200 characters, break into coherent subchunks with overlap
            if len(full_slide_content) > 1200:
                # Divide by paragraphs or lines
                lines = full_slide_content.split("\n\n")
                buf = []
                buf_len = 0
                sub_part = 1
                for line in lines:
                    buf.append(line)
                    buf_len += len(line)
                    if buf_len >= 800:
                        chunk_text = "\n\n".join(buf)
                        h = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                        chunks.append(
                            ExtractedChunk(
                                chunk_index=chunk_idx,
                                slide_number=slide_num,
                                section_path=f"{section_path} (Part {sub_part})",
                                chunk_type="slide",
                                content_text=chunk_text,
                                content_hash=h,
                                metadata_json={"is_visual_extraction": has_visual_extraction, "slide_title": slide_title},
                            )
                        )
                        chunk_idx += 1
                        total_text += "\n" + chunk_text
                        sub_part += 1
                        buf = [lines[0]] if lines else []  # Keep title for context
                        buf_len = len(buf[0]) if buf else 0
                if buf and len(buf) > 1:
                    chunk_text = "\n\n".join(buf)
                    h = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                    chunks.append(
                        ExtractedChunk(
                            chunk_index=chunk_idx,
                            slide_number=slide_num,
                            section_path=f"{section_path} (Part {sub_part})" if sub_part > 1 else section_path,
                            chunk_type="slide",
                            content_text=chunk_text,
                            content_hash=h,
                            metadata_json={"is_visual_extraction": has_visual_extraction, "slide_title": slide_title},
                        )
                    )
                    chunk_idx += 1
                    total_text += "\n" + chunk_text
            else:
                h = hashlib.sha256(full_slide_content.encode("utf-8")).hexdigest()
                chunks.append(
                    ExtractedChunk(
                        chunk_index=chunk_idx,
                        slide_number=slide_num,
                        section_path=section_path,
                        chunk_type="slide",
                        content_text=full_slide_content,
                        content_hash=h,
                        metadata_json={"is_visual_extraction": has_visual_extraction, "slide_title": slide_title},
                    )
                )
                chunk_idx += 1
                total_text += "\n" + full_slide_content

        total_text = total_text.strip()
        raw_checksum = hashlib.sha256(total_text.encode("utf-8")).hexdigest() if total_text else ""

        if not total_text or not chunks:
            warnings.append("Presentation contains no readable text or visual content.")
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
