"""Pipeline 1 — Download and convert emission documents.

Downloads emission documents from e-disclosure.ru and converts all of them
to Markdown format (no filename or header filters applied).

Reuses existing code from:
- EdisclosureService for company_id resolution
- EmissionDocumentRepository for DB access
- edisclosure_utils for downloading / ZIP extraction
- PdfConversionService (called directly, bypassing header/name filters)

Two modes:
- Initial load: processes all floater bonds that have no data directory.
- Update: re-processes only bonds that previously failed (no .md files).
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.core.exceptions import PdfConversionConnectionError
from app.repository.db.bond_float_params_repository import BondFloatParamsRepository
from app.repository.db.emission_document_repository import EmissionDocumentRepository
from app.repository.files.file_storage import FileStorage
from app.services.bonds_service import (
    get_emitent_inn_by_secid,
    get_floater_secids,
    get_reg_number_by_secid,
)
from app.services.edisclosure_service import EdisclosureService
from app.services.pdf_conversion_service import PdfConversionService
from app.utils.edisclosure_utils import (
    clean_markdown_after_pdf2md,
    download_emission_file,
    extract_zip_to_dir,
)
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
_MANIFEST_FILENAME: str = ".processed.json"

# MIME types supported for conversion.
_EXTENSION_MIME_MAP: Dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".rtf": "application/rtf",
}


def _get_pipeline_logger() -> logging.Logger:
    """Returns a logger that writes to a separate log file for the download pipeline."""
    from config.paths import BACKEND_DIR

    log_dir: Path = BACKEND_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger_name: str = "emission_doc_download_pipeline"
    pl_logger: logging.Logger = logging.getLogger(logger_name)
    if pl_logger.handlers:
        return pl_logger

    pl_logger.setLevel(logging.INFO)
    log_file: Path = log_dir / f"emission_doc_download_{datetime.now().strftime('%Y-%m-%d')}.log"
    fh: logging.FileHandler = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fmt: logging.Formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(fmt)
    pl_logger.addHandler(fh)
    pl_logger.propagate = False
    return pl_logger


class EmissionDocDownloadService:
    """Pipeline 1: download emission documents and convert ALL to Markdown.

    No filename-based or header-based filters are applied during conversion —
    every extracted document is converted and saved.
    """

    def __init__(self) -> None:
        self._file_storage: FileStorage = FileStorage()
        self._emission_doc_repo: EmissionDocumentRepository = EmissionDocumentRepository()
        self._edisclosure_service: EdisclosureService = EdisclosureService()
        self._float_params_repo: BondFloatParamsRepository = BondFloatParamsRepository()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def download_and_convert(
        self,
        secid: Optional[str] = None,
        limit: Optional[int] = None,
        rating: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Download and convert emission documents for floater bonds.

        Args:
            secid: If provided — process only the bond with this SECID.
            limit: Maximum number of bonds to process. None — all unprocessed / failed.
            rating: If set — only floaters with this credit rating.

        Returns:
            Summary dict with processing statistics.
        """
        pl_logger: logging.Logger = _get_pipeline_logger()

        if secid and secid.strip():
            return self._process_single_by_secid(secid.strip(), pl_logger)

        all_secids: List[str] = get_floater_secids(rating=rating)
        total_all: int = len(all_secids)

        # Determine which bonds need processing.
        to_process: List[str] = []
        already_done: int = 0
        for secid in all_secids:
            bond_dir: Path = _DATA_DIR / secid
            if self._is_bond_fully_processed(secid, bond_dir, pl_logger):
                already_done += 1
                continue
            to_process.append(secid)

        if limit is not None:
            to_process = to_process[:limit]

        total: int = len(to_process)
        pl_logger.info("=" * 60)
        pl_logger.info(
            "[DOWNLOAD PIPELINE START] Total floaters: %d, already done: %d, to process: %d",
            total_all, already_done, total,
        )
        print(
            f"[DOWNLOAD PIPELINE] Total floaters: {total_all}, "
            f"already done: {already_done}, to process: {total}",
            flush=True,
        )

        processed: int = 0
        succeeded: int = 0
        failed_secids: List[str] = []

        for idx, secid in enumerate(to_process, start=1):
            processed += 1
            try:
                ok: bool = self._process_single_bond(secid, pl_logger)
                if ok:
                    succeeded += 1
                    print(f"[DOWNLOAD] {idx}/{total} — {secid}: OK", flush=True)
                else:
                    failed_secids.append(secid)
                    print(f"[DOWNLOAD] {idx}/{total} — {secid}: no documents", flush=True)
            except PdfConversionConnectionError as exc:
                pl_logger.error(
                    "[PDF2MD ERROR] Pipeline stopped, secid=%s: %s", secid, exc, exc_info=True,
                )
                print(
                    f"[DOWNLOAD] Pipeline stopped: pdf2md connection error — {exc}",
                    flush=True,
                )
                raise
            except Exception as exc:
                pl_logger.error(
                    "[ERROR] secid=%s: %s", secid, exc, exc_info=True,
                )
                failed_secids.append(secid)
                print(f"[DOWNLOAD] {idx}/{total} — {secid}: error ({exc})", flush=True)

        summary: str = (
            f"[DOWNLOAD PIPELINE DONE] Processed: {processed}, "
            f"succeeded: {succeeded}, failed: {len(failed_secids)}"
        )
        pl_logger.info(summary)
        pl_logger.info("=" * 60)
        print(summary, flush=True)

        return {
            "status": "ok",
            "total_floaters": total_all,
            "already_done": already_done,
            "processed": processed,
            "succeeded": succeeded,
            "failed": len(failed_secids),
            "failed_secids": failed_secids,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_manifest(self, bond_dir: Path) -> Dict[str, List[str]]:
        """Load the archive-to-files mapping from the manifest file."""
        manifest_path = bond_dir / _MANIFEST_FILENAME
        if not manifest_path.exists():
            return {}
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Handle migrations from older formats if necessary
                if "archives" in data:
                    return data["archives"]
                if "processed_urls" in data:
                    return {url: [] for url in data["processed_urls"]}
                return {}
        except Exception:
            return {}

    def _save_manifest(self, bond_dir: Path, archives: Dict[str, List[str]]) -> None:
        """Save the archive-to-files mapping to the manifest file."""
        manifest_path = bond_dir / _MANIFEST_FILENAME
        bond_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump({"archives": archives}, f, indent=2)
        except Exception as exc:
            logging.error("Failed to save manifest to %s: %s", manifest_path, exc)

    def _cleanup_source_files(self, bond_dir: Path) -> None:
        """Delete all source documents (PDF, DOC, etc.) to ensure a clean state."""
        if not bond_dir.is_dir():
            return
        for ext in _EXTENSION_MIME_MAP.keys():
            # Remove files in both lower and upper case
            for f in bond_dir.glob(f"*{ext}"):
                f.unlink(missing_ok=True)
            for f in bond_dir.glob(f"*{ext.upper()}"):
                f.unlink(missing_ok=True)

    def _is_bond_fully_processed(
        self, secid: str, bond_dir: Path, pl_logger: logging.Logger
    ) -> bool:
        """Analyze if the bond's documents are fully downloaded and converted."""
        if not bond_dir.is_dir():
            return False

        # 1. Check against Manifest (URLs from DB)
        manifest = self._load_manifest(bond_dir)
        inn = get_emitent_inn_by_secid(secid)
        regnumber = get_reg_number_by_secid(secid)
        if not inn or not regnumber:
            return False

        db_records = self._emission_doc_repo.get_by_inn_and_reg_number(inn, regnumber)
        if not db_records:
            return True

        for rec in db_records:
            url = getattr(rec, "file_url", None) or rec.get("file_url")
            if url and url not in manifest:
                pl_logger.info("[%s] URL not in manifest: %s", secid, url)
                return False

        # 2. Check local files integrity for all archives in manifest
        for files in manifest.values():
            for f in files:
                if Path(f).suffix.lower() in _EXTENSION_MIME_MAP:
                    if not (bond_dir / Path(f).with_suffix(".md")).exists():
                        pl_logger.info("[%s] Incomplete: file '%s' has no .md", secid, f)
                        return False

        return True

    def _process_single_by_secid(
        self, secid: str, pl_logger: logging.Logger,
    ) -> Dict[str, Any]:
        """Process a single bond identified by its SECID."""
        try:
            ok: bool = self._process_single_bond(secid, pl_logger)
            return {
                "status": "ok",
                "secid": secid,
                "ok": ok,
            }
        except Exception as exc:
            pl_logger.error("Error processing secid %s: %s", secid, exc, exc_info=True)
            return {
                "status": "error",
                "secid": secid,
                "detail": str(exc),
            }

    def _process_single_bond(
        self, secid: str, pl_logger: logging.Logger,
    ) -> bool:
        """Download and convert emission documents for a single bond.

        Steps:
        1. Resolve INN and regnumber from DB.
        2. Download ZIP archives from emission_documents table.
        3. Extract files.
        4. Convert ALL extracted files with supported extensions to Markdown.

        Returns:
            True if ALL convertible files were successfully processed.
        """
        print(f"  [{secid}] Download pipeline start", flush=True)
        bond_data_dir: Path = _DATA_DIR / secid
        bond_data_dir.mkdir(parents=True, exist_ok=True)

        inn: Optional[str] = get_emitent_inn_by_secid(secid)
        if not inn:
            pl_logger.warning("[SKIP] secid=%s: emitent INN not found", secid)
            return False

        regnumber: Optional[str] = get_reg_number_by_secid(secid)
        if not regnumber or not regnumber.strip():
            pl_logger.warning("[SKIP] secid=%s: registration number not found", secid)
            return False

        # CLEANUP: Delete old source files and reset manifest to avoid
        # file multiplication and naming issues (_1, _2).
        self._cleanup_source_files(bond_data_dir)
        self._save_manifest(bond_data_dir, {})
        manifest: Dict[str, List[str]] = {}

        # --- Phase 1: Collect missing conversions from existing archives ---
        to_convert: List[str] = []
        for files in manifest.values():
            for f in files:
                if Path(f).suffix.lower() in _EXTENSION_MIME_MAP:
                    if not (bond_data_dir / Path(f).with_suffix(".md")).exists():
                        to_convert.append(f)

        # --- Phase 2: Download NEW archives ---
        print(f"  [{secid}] Phase 2: download new documents", flush=True)
        new_url_to_files: Dict[str, List[str]] = self._download_documents(
            inn, regnumber, bond_data_dir, pl_logger, secid
        )

        for url, files in new_url_to_files.items():
            manifest[url] = files
            for f in files:
                if Path(f).suffix.lower() in _EXTENSION_MIME_MAP:
                    if not (bond_data_dir / Path(f).with_suffix(".md")).exists():
                        to_convert.append(f)

        if not to_convert:
            # If nothing to convert, ensure manifest is up to date (e.g. all XLS files)
            self._save_manifest(bond_data_dir, manifest)
            return True

        # --- Phase 3: Selective Batch Conversion ---
        print(f"  [{secid}] Phase 3: convert {len(to_convert)} files", flush=True)
        md_filenames: List[str] = self._convert_all_to_markdown(
            to_convert, bond_data_dir, pl_logger, secid
        )

        for md_name in md_filenames:
            print(f"  [PDF2MD] Created: {md_name}", flush=True)

        # Only archives where ALL convertible files now exist as .md are considered fully processed
        self._save_manifest(bond_data_dir, manifest)

        success = len(md_filenames) == len(to_convert)
        pl_logger.info(
            "[DONE] secid=%s: requested=%d, md_files=%d, status=%s",
            secid,
            len(to_convert),
            len(md_filenames),
            "OK" if success else "INCOMPLETE",
        )
        return success

    def _download_documents(
        self,
        inn: str,
        regnumber: str,
        bond_data_dir: Path,
        pl_logger: logging.Logger,
        secid: str,
    ) -> Dict[str, List[str]]:
        """Download emission ZIP archives and extract files, skipping already processed URLs."""
        emission_records = self._emission_doc_repo.get_by_inn_and_reg_number(inn, regnumber)
        manifest = self._load_manifest(bond_data_dir)

        url_to_files: Dict[str, List[str]] = {}
        for rec in emission_records:
            file_url = getattr(rec, "file_url", None) or rec.get("file_url")
            if not file_url or file_url in manifest:
                continue

            content: Optional[bytes] = download_emission_file(file_url)
            if not content:
                continue

            extracted: List[str] = extract_zip_to_dir(content, bond_data_dir)
            if extracted:
                url_to_files[file_url] = extracted

        return url_to_files

    def _convert_all_to_markdown(
        self,
        filenames: List[str],
        base_dir: Path,
        pl_logger: logging.Logger,
        secid: str,
    ) -> List[str]:
        """Convert ALL extracted files to Markdown — no filename or header filters.

        Uses safe filenames for API communication to avoid crashes
        caused by long names, spaces, or non-ASCII characters.
        """
        import httpx

        safe_to_original: Dict[str, str] = {}
        files_payload: List[Any] = []

        for filename in filenames:
            file_path: Path = base_dir / filename
            ext: str = file_path.suffix.lower()
            mime_type: Optional[str] = _EXTENSION_MIME_MAP.get(ext)
            if mime_type is None:
                pl_logger.warning(
                    "[SKIP] secid=%s: unsupported extension '%s': %s",
                    secid,
                    ext,
                    file_path,
                )
                continue
            if not file_path.is_file():
                pl_logger.error("[SKIP] secid=%s: file not found: %s", secid, file_path)
                continue

            # Use a simple index-based safe name for the API (file_0.pdf, file_1.pdf, etc.)
            # This is the most robust way to avoid encoding/length issues with APIs.
            safe_name = f"file_{len(safe_to_original)}{ext}"
            safe_to_original[safe_name] = filename

            files_payload.append(
                ("files", (safe_name, file_path.read_bytes(), mime_type)),
            )

        if not files_payload:
            return []

        url: str = f"{settings.PDF2MD_BASE_URL.rstrip('/')}/api/v1/convert/batch"
        print(f"  [API] POST {url} (no timeout)", flush=True)
        try:
            with httpx.Client(timeout=None) as client:
                response: httpx.Response = client.post(url, files=files_payload)
                response.raise_for_status()
                body: Dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            message: str = f"Batch conversion error: {exc}"
            pl_logger.error(message)
            raise PdfConversionConnectionError(message, cause=exc) from exc

        results: List[Dict[str, Any]] = body.get("results", [])

        md_filenames: List[str] = []
        for item in results:
            returned_name: str = item.get("filename", "")

            # 1. Try exact match
            original_name = safe_to_original.get(returned_name)

            # 2. Try match without extension (some APIs strip it)
            if not original_name:
                returned_stem = Path(returned_name).stem
                for k, v in safe_to_original.items():
                    if Path(k).stem == returned_stem:
                        original_name = v
                        break

            # Fallback
            if not original_name:
                original_name = returned_name

            error: Optional[str] = item.get("error")
            markdown: Optional[str] = item.get("markdown")

            if error:
                pl_logger.error("Conversion error (original: %s): %s", original_name, error)
                continue

            if not markdown:
                pl_logger.warning("Empty markdown for %s", original_name)
                continue

            # Save using the ORIGINAL filename for local storage
            md_filename: str = Path(original_name).stem + ".md"
            markdown = clean_markdown_after_pdf2md(markdown)
            self._file_storage.save_text_file(base_dir / md_filename, markdown)
            pl_logger.info("[%s] Saved markdown: %s (from %s)", secid, md_filename, returned_name)
            md_filenames.append(md_filename)

        return md_filenames


_emission_doc_download_service: Optional[EmissionDocDownloadService] = None


def get_emission_doc_download_service() -> EmissionDocDownloadService:
    """Returns singleton EmissionDocDownloadService."""
    global _emission_doc_download_service
    if _emission_doc_download_service is None:
        _emission_doc_download_service = EmissionDocDownloadService()
    return _emission_doc_download_service
