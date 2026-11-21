"""Source 'corpus' : tu balances des fichiers dans un dossier, elle les ingère.

Formats supportés par fichier :
  - .txt / .md   -> un document = un fichier
  - .html / .htm -> un document = un fichier (tags stripés à la normalisation)
  - .pdf         -> texte extrait page par page (pypdf) -- pas d'OCR : un PDF
                     scanné sans texte (image pure) ressort vide, pas d'erreur
  - .json        -> soit un objet {"title":..., "text":...},
                     soit une liste de tels objets (plusieurs documents par fichier)
  - .jsonl       -> une ligne = un objet {"title":..., "text":...}
  - .csv         -> doit contenir une colonne 'text' (et idéalement 'title')
  - .xlsx        -> toutes les feuilles, cellule par cellule, texte concaténé
                     (pas de formules évaluées : valeurs affichées telles quelles)

Dépose simplement de nouveaux fichiers dans le dossier : au prochain cycle,
seuls les fichiers jamais vus (par hash de contenu, géré par le DocumentStore)
sont réellement traités.

Tout fichier d'extension non listée ci-dessus est ignoré silencieusement au
niveau du pipeline (pas d'erreur), d'où SUPPORTED_EXTS exposé plus bas : sert
à avertir l'utilisateur (webui) qu'un fichier déposé ne sera jamais traité.
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Iterable

from graphwatch.ingest.normalize import Document
from graphwatch.sources.base import Source

log = logging.getLogger(__name__)

TEXT_EXTS = {".txt", ".md"}
HTML_EXTS = {".html", ".htm"}
SPREADSHEET_EXTS = {".xlsx"}
SUPPORTED_EXTS = TEXT_EXTS | HTML_EXTS | SPREADSHEET_EXTS | {".pdf", ".json", ".jsonl", ".csv"}


class CorpusFolderSource(Source):
    def fetch(self) -> Iterable[Document]:
        path = self.options.get("path")
        if not path:
            raise ValueError(f"source corpus '{self.name}' sans 'path' dans la config")
        folder = Path(path)
        if not folder.exists():
            log.warning("dossier corpus introuvable pour %s: %s", self.name, folder)
            return []

        docs: list[Document] = []
        for f in sorted(folder.rglob("*")):
            if not f.is_file():
                continue
            try:
                docs.extend(self._read_file(f))
            except Exception as e:  # un fichier cassé ne doit pas bloquer tout le cycle
                log.warning("échec lecture %s: %s", f, e)
        return docs

    def _read_file(self, f: Path) -> list[Document]:
        ext = f.suffix.lower()

        if ext in TEXT_EXTS or ext in HTML_EXTS:
            text = f.read_text(encoding="utf-8", errors="ignore")
            return [Document(source_name=self.name, origin=str(f), title=f.stem, text=text)]

        if ext == ".pdf":
            text = self._extract_pdf_text(f)
            if not text.strip():
                log.warning("%s : aucun texte extrait (PDF scanné/image sans OCR ?)", f)
            return [Document(source_name=self.name, origin=str(f), title=f.stem, text=text)]

        if ext == ".json":
            raw = json.loads(f.read_text(encoding="utf-8", errors="ignore"))
            items = raw if isinstance(raw, list) else [raw]
            out = []
            for i, item in enumerate(items):
                out.append(
                    Document(
                        source_name=self.name,
                        origin=f"{f}#{i}",
                        title=str(item.get("title", f.stem)),
                        text=str(item.get("text", "")),
                    )
                )
            return out

        if ext == ".jsonl":
            out = []
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines()):
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                out.append(
                    Document(
                        source_name=self.name,
                        origin=f"{f}#{i}",
                        title=str(item.get("title", f"{f.stem}-{i}")),
                        text=str(item.get("text", "")),
                    )
                )
            return out

        if ext == ".csv":
            out = []
            with f.open(newline="", encoding="utf-8", errors="ignore") as fh:
                reader = csv.DictReader(fh)
                for i, row in enumerate(reader):
                    if "text" not in row:
                        raise ValueError(f"{f} n'a pas de colonne 'text'")
                    out.append(
                        Document(
                            source_name=self.name,
                            origin=f"{f}#{i}",
                            title=row.get("title", f"{f.stem}-{i}"),
                            text=row["text"],
                        )
                    )
            return out

        if ext in SPREADSHEET_EXTS:
            text = self._extract_xlsx_text(f)
            if not text.strip():
                log.warning("%s : aucun texte extrait (xlsx vide ?)", f)
            return [Document(source_name=self.name, origin=str(f), title=f.stem, text=text)]

        log.warning("%s : extension '%s' non supportée, fichier ignoré (voir SUPPORTED_EXTS)", f, ext)
        return []

    def _extract_xlsx_text(self, f: Path) -> str:
        import pandas as pd

        sheets = pd.read_excel(f, sheet_name=None, header=None, dtype=str)
        parts = []
        for sheet_name, df in sheets.items():
            parts.append(f"## {sheet_name}")
            for row in df.itertuples(index=False):
                cells = [str(c).strip() for c in row if c is not None and str(c).strip().lower() != "nan"]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts)

    def _extract_pdf_text(self, f: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(f))
        if reader.is_encrypted:
            try:
                reader.decrypt("")  # tente un mot de passe vide, sinon abandonne proprement
            except Exception:
                log.warning("%s : PDF chiffré, illisible sans mot de passe", f)
                return ""
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception as e:
                log.warning("%s : échec extraction d'une page (%s)", f, e)
        return "\n".join(pages)
