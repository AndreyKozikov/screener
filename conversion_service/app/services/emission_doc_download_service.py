"""Pipeline 1 — Download and convert emission documents.

Downloads emission documents from e-disclosure.ru and converts all of them
to Markdown format (no filename or header filters applied).

Features:
- Manifest-based tracking (per-URL status).
- Automatic cleanup of source files (PDF, DOCX, ZIP, RAR) after successful processing.
- RAR support (including multi-volume).
- Re-processing logic if manifest is missing.
"""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import rarfile
from app.core.exceptions import PdfConversionConnectionError
from app.repository.db.emission_document_repository import EmissionDocumentRepository
from app.repository.files.file_storage import FileStorage
from app.services.bonds_service import (
    get_emitent_inn_by_secid,
    get_all_bond_secids,
    get_reg_number_by_secid,
    get_all_bonds_metadata,
)
from app.services.pdf_conversion_service import PdfConversionService
from app.utils.edisclosure_utils import (
    clean_markdown_after_pdf2md,
    download_emission_file,
    extract_archive_to_dir,
    sanitize_filename,
)
from config.paths import DATA_DIR
from config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

_DATA_DIR: Path = DATA_DIR
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
    pl_logger.setLevel(logging.INFO)
    log_file: Path = log_dir / f"emission_doc_download_{datetime.now().strftime('%Y-%m-%d')}.log"
    fmt: logging.Formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    has_file_handler: bool = any(
        isinstance(handler, logging.FileHandler)
        and getattr(handler, "baseFilename", None) == str(log_file)
        for handler in pl_logger.handlers
    )
    if not has_file_handler:
        fh: logging.FileHandler = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)
        pl_logger.addHandler(fh)

    has_console_handler: bool = any(
        getattr(handler, "_emission_doc_console", False)
        for handler in pl_logger.handlers
    )
    if not has_console_handler:
        ch: logging.StreamHandler = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        setattr(ch, "_emission_doc_console", True)
        pl_logger.addHandler(ch)

    pl_logger.propagate = False
    return pl_logger


class EmissionDocDownloadService:
    """Pipeline 1: download emission documents and convert ALL to Markdown.

    Maintains a manifest in each bond directory to track processed URLs.
    Deletes source files (PDFs, archives) after successful Markdown conversion.
    """

    def __init__(self) -> None:
        self._file_storage: FileStorage = FileStorage()
        self._emission_doc_repo: EmissionDocumentRepository = EmissionDocumentRepository()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def download_and_convert(
        self,
        secid: Optional[str] = None,
        limit: Optional[int] = None,
        rating: Optional[str] = None,
        force_recheck: bool = False,
        keep_source_files: bool = True,
    ) -> Dict[str, Any]:
        """Download and convert emission documents for bonds.

        Args:
            secid: If provided — process only the bond with this SECID.
            limit: Maximum number of bonds to process. None — all unprocessed / failed.
            rating: If set — only bonds with this credit rating.
            force_recheck: If True — checks all bonds completeness even if marked completed.
            keep_source_files: If False — deletes source files after successful conversion.

        Returns:
            Summary dict with processing statistics.
        """
        pl_logger: logging.Logger = _get_pipeline_logger()

        if secid and secid.strip():
            sid = secid.strip()
            inn = get_emitent_inn_by_secid(sid)
            reg_number = get_reg_number_by_secid(sid)
            expected_urls = None
            if inn and reg_number:
                db_records = self._emission_doc_repo.get_by_inn_and_reg_number(inn, reg_number)
                expected_urls = [str(rec["file_url"]).strip() for rec in db_records if rec.get("file_url")]

            return self._process_single_by_secid(
                sid,
                pl_logger,
                force_recheck=force_recheck,
                keep_source_files=keep_source_files,
                inn=inn,
                reg_number=reg_number,
                expected_urls=expected_urls,
            )

        # Пакетное извлечение метаданных и документов для оптимизации проверки
        bonds_metadata = {}
        all_docs_by_metadata = {}
        if force_recheck:
            bonds_metadata = get_all_bonds_metadata(rating=rating)
            all_docs_by_metadata = self._emission_doc_repo.get_all_documents_by_metadata()

        all_secids: List[str] = get_all_bond_secids(rating=rating)
        total_all: int = len(all_secids)

        # Determine which bonds need processing.
        to_process: List[str] = []
        already_done: int = 0
        for sid in all_secids:
            bond_dir: Path = _DATA_DIR / sid
            inn, reg_number = bonds_metadata.get(sid, (None, None))
            expected_urls = None
            if inn and reg_number:
                expected_urls = all_docs_by_metadata.get((inn, reg_number))

            if self._is_bond_fully_processed(
                sid,
                bond_dir,
                pl_logger,
                force_recheck=force_recheck,
                inn=inn,
                reg_number=reg_number,
                expected_urls=expected_urls,
            ):
                already_done += 1
                continue
            to_process.append(sid)

        if limit is not None:
            to_process = to_process[:limit]

        total: int = len(to_process)
        pl_logger.info("=" * 60)
        pl_logger.info(
            "[DOWNLOAD PIPELINE START] Total bonds: %d, already done: %d, to process: %d",
            total_all, already_done, total,
        )
        print(
            f"[DOWNLOAD PIPELINE] Total bonds: {total_all}, "
            f"already done: {already_done}, to process: {total}",
            flush=True,
        )

        processed: int = 0
        succeeded: int = 0
        failed_secids: List[str] = []

        for idx, sid in enumerate(to_process, start=1):
            processed += 1
            inn, reg_number = bonds_metadata.get(sid, (None, None))
            expected_urls = None
            if inn and reg_number:
                expected_urls = all_docs_by_metadata.get((inn, reg_number))

            try:
                ok: bool = self._process_single_bond(
                    sid,
                    pl_logger,
                    force_recheck=force_recheck,
                    keep_source_files=keep_source_files,
                    inn=inn,
                    reg_number=reg_number,
                    expected_urls=expected_urls,
                )
                if ok:
                    succeeded += 1
                    print(f"[DOWNLOAD] {idx}/{total} — {sid}: OK", flush=True)
                else:
                    failed_secids.append(sid)
                    print(f"[DOWNLOAD] {idx}/{total} — {sid}: incomplete", flush=True)
            except PdfConversionConnectionError as exc:
                pl_logger.error(
                    "[PDF2MD ERROR] Pipeline stopped, secid=%s: %s", sid, exc, exc_info=True,
                )
                print(
                    f"[DOWNLOAD] Pipeline stopped: pdf2md connection error — {exc}",
                    flush=True,
                )
                raise
            except Exception as exc:
                pl_logger.error(
                    "[ERROR] secid=%s: %s", sid, exc, exc_info=True,
                )
                failed_secids.append(sid)
                print(f"[DOWNLOAD] {idx}/{total} — {sid}: error ({exc})", flush=True)

        summary: str = (
            f"[DOWNLOAD PIPELINE DONE] Processed: {processed}, "
            f"succeeded: {succeeded}, failed: {len(failed_secids)}"
        )
        pl_logger.info(summary)
        pl_logger.info("=" * 60)
        print(summary, flush=True)

        return {
            "status": "ok",
            "total_bonds": total_all,
            "already_done": already_done,
            "processed": processed,
            "succeeded": succeeded,
            "failed": len(failed_secids),
            "failed_secids": failed_secids,
        }


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_archive_entry(entry: Any) -> Dict[str, Any]:
        """Normalize one manifest archive entry from legacy formats."""
        processed_at = datetime.now().isoformat()

        if isinstance(entry, list):
            files = [str(item) for item in entry if item]
            return {
                "status": "completed" if files else "downloaded",
                "files": files,
                "files_mapping": {name: name for name in files},
                "converted_files": [
                    name for name in files if Path(name).suffix.lower() in _EXTENSION_MIME_MAP
                ],
                "processed_at": processed_at,
                "error": None,
            }

        if not isinstance(entry, dict):
            return {
                "status": "error",
                "files": [],
                "files_mapping": {},
                "converted_files": [],
                "processed_at": processed_at,
                "error": f"Unsupported manifest entry type: {type(entry).__name__}",
            }

        files = entry.get("files", [])
        if not isinstance(files, list):
            files = []
        entry["files"] = files

        converted_files = entry.get("converted_files")
        if not isinstance(converted_files, list):
            entry["converted_files"] = [
                name for name in files if Path(name).suffix.lower() in _EXTENSION_MIME_MAP
            ]

        files_mapping = entry.get("files_mapping")
        if not isinstance(files_mapping, dict):
            entry["files_mapping"] = {name: name for name in files}

        if "processed_at" not in entry:
            entry["processed_at"] = processed_at

        if "error" not in entry:
            entry["error"] = None

        return entry

    def _load_manifest(self, bond_dir: Path) -> Dict[str, Any]:
        """Load the processing manifest from the bond directory."""
        manifest_path = bond_dir / _MANIFEST_FILENAME
        default_manifest = {"archives": {}, "fully_processed": False}
        if not manifest_path.exists():
            return default_manifest
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return default_manifest

                # Case 1: Very old format (url -> [files])
                if "archives" not in data and data:
                    new_archives = {}
                    for url, files in data.items():
                        if isinstance(files, list):
                            new_archives[url] = {
                                "status": "completed" if files else "downloaded",
                                "files": files,
                                "processed_at": datetime.now().isoformat(),
                                "error": None,
                            }
                    return {"archives": new_archives, "fully_processed": False}

                # Case 2: Ensure "archives" is a dict and migrate old entries
                archives = data.get("archives")
                if not isinstance(archives, dict):
                    data["archives"] = {}
                    archives = data["archives"]

                # Migration: upgrade legacy list entries and normalize current schema
                for url, entry in list(archives.items()):
                    archives[url] = self._normalize_archive_entry(entry)

                return data
        except Exception:
            return default_manifest

    def _save_manifest(self, bond_dir: Path, manifest: Dict[str, Any]) -> None:
        """Save the processing manifest to the bond directory."""
        manifest_path = bond_dir / _MANIFEST_FILENAME
        bond_dir.mkdir(parents=True, exist_ok=True)
        manifest["updated_at"] = datetime.now().isoformat()
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logging.error("Failed to save manifest to %s: %s", manifest_path, exc)

    def _cleanup_source_files(self, bond_dir: Path, filenames: Optional[List[str]] = None) -> None:
        """Delete source documents (PDF, DOC, ZIP, RAR)."""
        if not bond_dir.is_dir():
            return
        
        # 1. Delete specific filenames if provided
        if filenames:
            for fname in filenames:
                fpath = bond_dir / fname
                if fpath.exists():
                    try:
                        fpath.unlink()
                    except Exception:
                        pass
        
        # 2. General cleanup for common extensions (only if no specific filenames were requested to be deleted)
        if not filenames:
            extensions = list(_EXTENSION_MIME_MAP.keys()) + [".zip", ".rar", ".7z"]
            for ext in extensions:
                for f in bond_dir.glob(f"*{ext}"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
                for f in bond_dir.glob(f"*{ext.upper()}"):
                    try:
                        f.unlink()
                    except Exception:
                        pass

    def _is_bond_fully_processed(
        self,
        secid: str,
        bond_dir: Path,
        pl_logger: logging.Logger,
        force_recheck: bool = False,
        inn: Optional[str] = None,
        reg_number: Optional[str] = None,
        expected_urls: Optional[List[str]] = None,
    ) -> bool:
        """Analyze if the bond's documents are fully downloaded and converted."""
        if not bond_dir.is_dir():
            return False

        manifest = self._load_manifest(bond_dir)
        if not force_recheck and manifest.get("fully_processed"):
            return True

        if not inn or not reg_number:
            inn = get_emitent_inn_by_secid(secid)
            reg_number = get_reg_number_by_secid(secid)

        if not inn or not reg_number:
            return False

        if expected_urls is None:
            db_records = self._emission_doc_repo.get_by_inn_and_reg_number(inn, reg_number)
            urls = [str(rec["file_url"]).strip() for rec in db_records if rec.get("file_url")]
        else:
            urls = expected_urls

        if not urls:
            if manifest.get("fully_processed") is not True:
                manifest["fully_processed"] = True
                self._save_manifest(bond_dir, manifest)
            return True

        archives = manifest.get("archives")
        if not isinstance(archives, dict):
            archives = {}

        for url in urls:
            entry = archives.get(url)
            is_completed = False

            if (
                isinstance(entry, dict)
                and entry.get("status") == "completed"
                and not entry.get("error")
            ):
                files = entry.get("files", [])
                converted = entry.get("converted_files", [])
                
                # Строгая проверка: списки файлов не должны быть пустыми
                if isinstance(files, list) and files and isinstance(converted, list) and converted:
                    all_md_needed = [f for f in files if Path(f).suffix.lower() in _EXTENSION_MIME_MAP]
                    if not all_md_needed:
                        is_completed = True
                    else:
                        all_md_exist = True
                        for f in all_md_needed:
                            md_file = bond_dir / Path(f).with_suffix(".md")
                            if f not in converted or not md_file.exists():
                                all_md_exist = False
                                break
                        if all_md_exist:
                            is_completed = True

            if not is_completed:
                pl_logger.debug("[%s] URL not fully processed: %s", secid, url)
                # Первым делом делаем отметку, что документы обработаны не полностью
                if manifest.get("fully_processed") is not False:
                    manifest["fully_processed"] = False
                    self._save_manifest(bond_dir, manifest)
                return False

        # If we reached here, all URLs are completed. Mark as fully processed.
        if manifest.get("fully_processed") is not True:
            manifest["fully_processed"] = True
            manifest["archives"] = archives
            self._save_manifest(bond_dir, manifest)
        return True


    def _process_single_by_secid(
        self,
        secid: str,
        pl_logger: logging.Logger,
        force_recheck: bool = False,
        keep_source_files: bool = True,
        inn: Optional[str] = None,
        reg_number: Optional[str] = None,
        expected_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Process a single bond identified by its SECID."""
        try:
            ok: bool = self._process_single_bond(
                secid,
                pl_logger,
                force_recheck=force_recheck,
                keep_source_files=keep_source_files,
                inn=inn,
                reg_number=reg_number,
                expected_urls=expected_urls,
            )
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
        self,
        secid: str,
        pl_logger: logging.Logger,
        force_recheck: bool = False,
        keep_source_files: bool = True,
        inn: Optional[str] = None,
        reg_number: Optional[str] = None,
        expected_urls: Optional[List[str]] = None,
    ) -> bool:
        """Download and convert emission documents for a single bond.

        Logic for multi-volume RAR:
        - Download all missing URLs to local files.
        - Iterate through archives.
        - If it's the first volume of a RAR, extract the whole set.
        - Delete all volumes in the set.
        - Mark all involved URLs as completed.
        """
        print(f"  [{secid}] Download pipeline start", flush=True)
        bond_data_dir: Path = _DATA_DIR / secid
        bond_data_dir.mkdir(parents=True, exist_ok=True)

        if not inn or not reg_number:
            inn = get_emitent_inn_by_secid(secid)
            reg_number = get_reg_number_by_secid(secid)

        if not inn or not reg_number:
            pl_logger.warning("[SKIP] secid=%s: metadata missing", secid)
            return False

        manifest: Dict[str, Any] = self._load_manifest(bond_data_dir)
        archives: Dict[str, Any] = manifest["archives"]

        if expected_urls is None:
            db_records = self._emission_doc_repo.get_by_inn_and_reg_number(inn, reg_number)
            urls = [str(rec["file_url"]).strip() for rec in db_records if rec.get("file_url")]
        else:
            urls = expected_urls

        if not urls:
            return True

        # --- Phase 1: Download missing URLs and collect all local files for processing ---
        pl_logger.info("[%s] Phase 1/4: Checking/Downloading files", secid)
        path_to_url: Dict[str, str] = {}  # For RAR volume mapping

        # We'll collect all files that need to be processed (extracted or converted)
        files_to_process: Set[Path] = set()
        any_download_error = False

        for url in urls:
            if not url:
                continue

            # Extra safety check for archives type
            if not isinstance(archives, dict):
                archives = {}

            entry = archives.get(url)
            if entry is not None and not isinstance(entry, dict):
                entry = self._normalize_archive_entry(entry)
                archives[url] = entry
            is_completed = False
            if (
                isinstance(entry, dict)
                and entry.get("status") == "completed"
                and not entry.get("error")
            ):
                files = entry.get("files", [])
                converted = entry.get("converted_files", [])
                if isinstance(files, list) and files and isinstance(converted, list) and converted:
                    all_md_needed = [f for f in files if Path(f).suffix.lower() in _EXTENSION_MIME_MAP]
                    if not all_md_needed:
                        is_completed = True
                    else:
                        all_md_exist = True
                        for f in all_md_needed:
                            md_file = bond_data_dir / Path(f).with_suffix(".md")
                            if f not in converted or not md_file.exists():
                                all_md_exist = False
                                break
                        if all_md_exist:
                            is_completed = True

                if not is_completed:
                    entry["status"] = "error"
                    entry["error"] = "Missing physical files or empty file lists (recheck triggered)"
                    manifest["fully_processed"] = False
                    self._save_manifest(bond_data_dir, manifest)

            if is_completed:
                continue

            # Determine local filename (initial guess)
            initial_filename = (
                url.split("/")[-1].split("?")[0] or f"file_{hash(url)}.bin"
            )
            if "type=3" in url and not initial_filename.lower().endswith(".zip"):
                initial_filename += ".zip"

            safe_initial_filename = sanitize_filename(initial_filename)
            local_path = bond_data_dir / safe_initial_filename
            if not local_path.exists():
                # Try to use company page as referer if we can find it
                referer = None
                inn = get_emitent_inn_by_secid(secid)
                if inn:
                    # This is a guess, but often helps
                    referer = f"https://www.e-disclosure.ru/portal/company.aspx?id={inn}"

                try:
                    content, real_filename = download_emission_file(url, referer=referer)
                    if content:
                        if real_filename:
                            safe_real_filename = sanitize_filename(real_filename)
                            local_path = bond_data_dir / safe_real_filename
                            archives.setdefault(url, {}).setdefault("files_mapping", {})[safe_real_filename] = real_filename
                        else:
                            archives.setdefault(url, {}).setdefault("files_mapping", {})[safe_initial_filename] = initial_filename
                            
                        local_path.write_bytes(content)
                        # Clear error if it was there
                        if url in archives:
                            archives[url]["error"] = None
                    else:
                        pl_logger.error("[%s] Failed to download: %s", secid, url)
                        any_download_error = True
                        archives[url] = {
                            "status": "error",
                            "error": "Download failed (no content)",
                            "processed_at": datetime.now().isoformat(),
                        }
                        continue
                except Exception as e:
                    pl_logger.error("[%s] Exception during download %s: %s", secid, url, e)
                    any_download_error = True
                    archives[url] = {
                        "status": "error",
                        "error": f"Download exception: {str(e)}",
                        "processed_at": datetime.now().isoformat(),
                    }
                    continue

            if local_path.exists():
                files_to_process.add(local_path)
                path_to_url[str(local_path.absolute())] = url

        # Also add any existing source files in the directory that are not yet completed
        for ext in list(_EXTENSION_MIME_MAP.keys()) + [".zip", ".rar", ".7z"]:
            for f in bond_data_dir.glob(f"*{ext}"):
                files_to_process.add(f)
            for f in bond_data_dir.glob(f"*{ext.upper()}"):
                files_to_process.add(f)

        if not files_to_process:
            return self._is_bond_fully_processed(
                secid,
                bond_data_dir,
                pl_logger,
                force_recheck=force_recheck,
                inn=inn,
                reg_number=reg_number,
                expected_urls=urls,
            )

        # --- Phase 2: Extraction ---
        pl_logger.info("[%s] Phase 2/4: Extracting archives", secid)
        extracted_all: Set[str] = set()
        any_error = any_download_error

        for local_path in list(files_to_process):
            ext = local_path.suffix.lower()
            
            if ext in _EXTENSION_MIME_MAP:
                # Direct document, add to set for phase 3
                extracted_all.add(local_path.name)
                continue

            if ext == ".zip":
                extracted = extract_archive_to_dir(local_path, bond_data_dir)
                if extracted:
                    extracted_all.update(extracted.keys())
                    # Mark URL as completed if we know it
                    url = path_to_url.get(str(local_path.absolute()))
                    if url:
                        entry = archives.setdefault(url, {"status": "downloaded", "files": list(extracted.keys())})
                        entry["status"] = "downloaded"
                        entry["files"] = list(extracted.keys())
                        entry["files_mapping"] = extracted
                        entry["processed_at"] = datetime.now().isoformat()
                    # local_path.unlink(missing_ok=True)
                else:
                    any_error = True
                    url = path_to_url.get(str(local_path.absolute()))
                    pl_logger.warning(
                        "[%s] ZIP extraction produced no files: %s (url=%s)",
                        secid,
                        local_path.name,
                        url or "unknown",
                    )
                    if url:
                        entry = archives.setdefault(
                            url, {"status": "error", "processed_at": datetime.now().isoformat()}
                        )
                        entry["status"] = "error"
                        entry["error"] = f"ZIP extraction failed: {local_path.name}"
                continue

            if ext == ".7z":
                extracted = extract_archive_to_dir(local_path, bond_data_dir)
                if extracted:
                    extracted_all.update(extracted.keys())
                    # Mark URL as completed if we know it
                    url = path_to_url.get(str(local_path.absolute()))
                    if url:
                        entry = archives.setdefault(url, {"status": "downloaded", "files": list(extracted.keys())})
                        entry["status"] = "downloaded"
                        entry["files"] = list(extracted.keys())
                        entry["files_mapping"] = extracted
                        entry["processed_at"] = datetime.now().isoformat()
                else:
                    any_error = True
                    url = path_to_url.get(str(local_path.absolute()))
                    pl_logger.warning(
                        "[%s] 7Z extraction produced no files: %s (url=%s)",
                        secid,
                        local_path.name,
                        url or "unknown",
                    )
                    if url:
                        entry = archives.setdefault(
                            url, {"status": "error", "processed_at": datetime.now().isoformat()}
                        )
                        entry["status"] = "error"
                        entry["error"] = f"7Z extraction failed: {local_path.name}"
                continue

            if ext == ".rar":
                try:
                    # Проверяем, является ли файл частью многотомного архива и не первым томом.
                    # Для RAR многотомники обычно имеют расширения .part1.rar, .part2.rar или .r00, .r01 и т.д.
                    # Библиотека rarfile при открытии любого тома пытается найти остальные,
                    # но для извлечения лучше начинать с первого.
                    
                    is_rar_volume = False
                    is_first_volume = True
                    
                    # Паттерны для многотомных архивов
                    if re.search(r'\.part(\d+)\.rar$', local_path.name, re.I):
                        is_rar_volume = True
                        m = re.search(r'\.part(\d+)\.rar$', local_path.name, re.I)
                        if m and m.group(1) != "1" and m.group(1) != "01":
                            is_first_volume = False
                    elif re.search(r'\.r(\d+)$', local_path.name, re.I):
                        is_rar_volume = True
                        # .rar - обычно первый, .r00 или .r01 - последующие (зависит от версии RAR)
                        is_first_volume = False

                    if is_rar_volume and not is_first_volume:
                        pl_logger.info("[%s] Skipping RAR volume %s (not the first volume)", secid, local_path.name)
                        continue

                    with rarfile.RarFile(local_path) as rf:
                        # Дополнительная проверка через саму библиотеку, если это возможно
                        try:
                            # В некоторых версиях rarfile есть rf.needs_volume() или проверка через infolist
                            if hasattr(rf, 'volumelist'):
                                volumes = rf.volumelist()
                                if volumes and Path(volumes[0]).name != local_path.name:
                                    # Если мы по имени не определили, что это не первый том, но библиотека говорит обратное
                                    pl_logger.info("[%s] Skipping RAR volume %s (library says not first)", secid, local_path.name)
                                    continue
                        except Exception:
                            pass

                        # Проверяем наличие всех томов перед извлечением
                        try:
                            volumes = rf.volumelist()
                            missing_volumes = []
                            for vol_name in volumes:
                                vol_path = Path(vol_name)
                                if not vol_path.is_absolute():
                                    vol_path = local_path.parent / vol_name
                                if not vol_path.exists():
                                    missing_volumes.append(vol_path.name)
                            
                            if missing_volumes:
                                pl_logger.warning("[%s] Cannot extract RAR %s: missing volumes: %s",
                                               secid, local_path.name, ", ".join(missing_volumes))
                                any_error = True
                                url = path_to_url.get(str(local_path.absolute()))
                                if url:
                                    entry = archives.setdefault(
                                        url,
                                        {"status": "error", "processed_at": datetime.now().isoformat()},
                                    )
                                    entry["status"] = "error"
                                    entry["error"] = f"RAR missing volumes: {', '.join(missing_volumes)}"
                                continue
                        except Exception as e:
                            pl_logger.error("[%s] Error checking RAR volumes for %s: %s", secid, local_path.name, e)

                        extracted = extract_archive_to_dir(local_path, bond_data_dir)
                        if extracted:
                            extracted_all.update(extracted.keys())
                            # Повторно получаем список томов для обновления манифеста
                            try:
                                volumes = rf.volumelist()
                                for vol_name in volumes:
                                    vol_path = Path(vol_name)
                                    if not vol_path.is_absolute():
                                        vol_path = local_path.parent / vol_name
                                    
                                    v_url = path_to_url.get(str(vol_path.absolute()))
                                    if v_url:
                                        entry = archives.setdefault(v_url, {"status": "downloaded", "files": list(extracted.keys())})
                                        entry["status"] = "downloaded"
                                        entry["files"] = list(extracted.keys())
                                        entry["files_mapping"] = extracted
                                        entry["processed_at"] = datetime.now().isoformat()
                            except Exception:
                                pass
                        else:
                            any_error = True
                            url = path_to_url.get(str(local_path.absolute()))
                            if url:
                                entry = archives.setdefault(
                                    url, {"status": "error", "processed_at": datetime.now().isoformat()}
                                )
                                entry["status"] = "error"
                                entry["error"] = f"RAR extraction failed: {local_path.name}"
                except Exception as exc:
                    pl_logger.error("[%s] RAR error on %s: %s", secid, local_path.name, exc)
                    any_error = True
                    url = path_to_url.get(str(local_path.absolute()))
                    if url:
                        entry = archives.setdefault(
                            url, {"status": "error", "processed_at": datetime.now().isoformat()}
                        )
                        entry["status"] = "error"
                        entry["error"] = f"RAR exception: {str(exc)}"
                continue

            # If we reached here, the file extension is not supported
            any_error = True
            url = path_to_url.get(str(local_path.absolute()))
            pl_logger.warning(
                "[%s] Unsupported file extension: %s (url=%s)",
                secid,
                local_path.name,
                url or "unknown",
            )
            if url:
                entry = archives.setdefault(
                    url, {"status": "error", "processed_at": datetime.now().isoformat()}
                )
                entry["status"] = "error"
                entry["error"] = f"Unsupported file extension: {local_path.name}"

        # --- Phase 3: Save intermediate manifest before conversion ---
        pl_logger.info("[%s] Phase 3/4: Saving intermediate manifest", secid)
        
        # Ensure all direct downloads are also in the manifest
        for local_path_abs, url in path_to_url.items():
            local_path = Path(local_path_abs)
            if local_path.suffix.lower() in _EXTENSION_MIME_MAP:
                if url not in archives or "files" not in archives[url]:
                    entry = archives.setdefault(url, {})
                    entry["status"] = "downloaded"
                    entry["files"] = [local_path.name]
                    entry.setdefault("files_mapping", {})[local_path.name] = local_path.name
                    entry["processed_at"] = datetime.now().isoformat()

        manifest["fully_processed"] = False
        self._save_manifest(bond_data_dir, manifest)

        # --- Phase 4: Conversion ---
        pl_logger.info("[%s] Phase 4/4: Converting documents", secid)
        
        # We iterate over archives in manifest to track progress per file
        manifest = self._load_manifest(bond_data_dir)
        archives = manifest.get("archives", {})
        
        for url, entry in archives.items():
            if entry.get("status") == "completed" and not entry.get("error"):
                continue
            
            files = entry.get("files", [])
            converted = entry.get("converted_files", [])
            if not isinstance(converted, list):
                converted = []
            
            all_converted = True
            for f in files:
                if Path(f).suffix.lower() not in _EXTENSION_MIME_MAP:
                    continue
                
                # Skip if already converted according to manifest AND file exists
                md_filename = Path(f).stem + ".md"
                if f in converted and (bond_data_dir / md_filename).exists():
                    continue
                
                # Convert single file
                ok = self._convert_single_to_markdown(f, bond_data_dir, pl_logger, secid)
                if ok:
                    if f not in converted:
                        converted.append(f)
                    entry["converted_files"] = converted
                    self._save_manifest(bond_data_dir, manifest)
                else:
                    all_converted = False
                    any_error = True
                    entry["status"] = "error"
                    entry["error"] = f"Conversion failed for {f}"
            
            # If all files for this URL are converted, mark URL as completed
            files_to_convert = [f for f in files if Path(f).suffix.lower() in _EXTENSION_MIME_MAP]
            if (
                all_converted
                and (not files_to_convert or len(converted) >= len(files_to_convert))
                and (files_to_convert or not entry.get("error"))
            ):
                entry["status"] = "completed"
                entry["error"] = None
                self._save_manifest(bond_data_dir, manifest)

        # --- Phase 5: Final verification ---
        # Read manifest again to get the full list of files to check
        manifest = self._load_manifest(bond_data_dir)
        archives = manifest.get("archives", {})
        
        all_md_present = True
        incomplete_entries: List[Tuple[str, str, Optional[str], List[str], List[str]]] = []
        if not archives:
            all_md_present = False
        else:
            for url, entry in archives.items():
                status = entry.get("status")
                error = entry.get("error")
                files = entry.get("files", [])
                converted_files = entry.get("converted_files", [])
                if status != "completed" or error:
                    all_md_present = False
                    incomplete_entries.append(
                        (url, str(status), error, list(files), list(converted_files))
                    )
        
        if all_md_present and not any_error:
            manifest["fully_processed"] = True
        else:
            manifest["fully_processed"] = False
            if not archives:
                pl_logger.warning("[%s] No files found in manifest to verify", secid)
            else:
                for url, status, error, files, converted_files in incomplete_entries:
                    pl_logger.warning(
                        "[%s] Incomplete archive: status=%s, error=%s, files=%s, converted=%s, url=%s",
                        secid,
                        status,
                        error or "-",
                        files,
                        converted_files,
                        url,
                    )

        self._save_manifest(bond_data_dir, manifest)

        # --- Phase 6: Cleanup source files if requested ---
        if not keep_source_files and manifest.get("fully_processed"):
            pl_logger.info("[%s] Phase 6/6: Cleaning up source files", secid)
            self._cleanup_source_files(bond_data_dir)
        
        return manifest.get("fully_processed", False)

    def _convert_single_to_markdown(
        self,
        filename: str,
        base_dir: Path,
        pl_logger: logging.Logger,
        secid: str,
    ) -> bool:
        """Convert a single file to Markdown via PDF2MD service."""
        import httpx

        file_path: Path = base_dir / filename
        ext: str = file_path.suffix.lower()
        mime_type: Optional[str] = _EXTENSION_MIME_MAP.get(ext)
        
        if mime_type is None or not file_path.is_file():
            return False

        # Используем условное имя для передачи (например, 1.pdf)
        # Это помогает избежать проблем с кодировкой кириллицы в именах файлов
        temp_name = f"1{ext}"
        files_payload = [("files", (temp_name, file_path.read_bytes(), mime_type))]
        url: str = f"{settings.PDF2MD_BASE_URL.rstrip('/')}/api/v1/convert/batch"
        
        try:
            with httpx.Client(timeout=None) as client:
                response: httpx.Response = client.post(url, files=files_payload)
                response.raise_for_status()
                body: Dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            message: str = f"Conversion error for {filename}: {exc}"
            pl_logger.error(message)
            # We don't raise here to allow processing other files,
            # but Phase 4 will catch any_error
            return False

        results: List[Dict[str, Any]] = body.get("results", [])
        if not results:
            return False
            
        item = results[0]
        error: Optional[str] = item.get("error")
        markdown: Optional[str] = item.get("markdown")

        if error:
            pl_logger.error("Conversion error (%s): %s", filename, error)
            return False

        if markdown:
            md_filename: str = Path(filename).stem + ".md"
            markdown = clean_markdown_after_pdf2md(markdown)
            self._file_storage.save_text_file(base_dir / md_filename, markdown)
            return True
            
        return False


_emission_doc_download_service: Optional[EmissionDocDownloadService] = None


def get_emission_doc_download_service() -> EmissionDocDownloadService:
    """Returns singleton EmissionDocDownloadService."""
    global _emission_doc_download_service
    if _emission_doc_download_service is None:
        _emission_doc_download_service = EmissionDocDownloadService()
    return _emission_doc_download_service
