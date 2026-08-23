from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

from .repo_context import (
    RepoContextError,
    _is_manifest_file,
    _is_plan_candidate_file,
    _iter_repo_files,
    _looks_like_test_path,
    _project_type_for_path,
    _project_type_for_source,
    _related_test_paths,
    _resolve_requested_path,
)


INDEX_VERSION = "repo-rag-v1"

_STOPWORDS = {
    "about",
    "after",
    "and",
    "are",
    "because",
    "before",
    "can",
    "change",
    "code",
    "does",
    "file",
    "fix",
    "for",
    "from",
    "how",
    "into",
    "make",
    "need",
    "needs",
    "not",
    "that",
    "the",
    "this",
    "use",
    "what",
    "when",
    "where",
    "with",
}

_SECRET_LINE_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|private[_-]?key)\b\s*[:=]"
)


@dataclass(frozen=True)
class _IndexedDocument:
    path: str
    kind: str
    project_type: str | None
    size_bytes: int
    line_count: int
    sha256: str
    symbols: tuple[str, ...]
    imports: tuple[str, ...]
    content_terms: dict[str, int]
    text_preview: str


def build_repo_rag_index(
    *,
    root: str,
    max_scan_files: int = 5000,
    max_file_bytes: int = 120000,
) -> dict[str, Any]:
    documents, skipped, scanned_count = _scan_documents(
        root=root,
        max_scan_files=max_scan_files,
        max_file_bytes=max_file_bytes,
    )
    response_documents = [_document_response(document) for document in documents]
    index_id = _index_hash(documents)
    project_types = sorted(
        {
            document.project_type
            for document in documents
            if document.project_type is not None
        }
    )
    return {
        "source": "biber_repo_rag_index",
        "ok": True,
        "index_version": INDEX_VERSION,
        "index_id": index_id,
        "scanned_files": scanned_count,
        "indexed_files": len(response_documents),
        "skipped_files": len(skipped),
        "detected_project_types": project_types,
        "documents": response_documents,
        "skipped": skipped,
        "summary": (
            f"Indexed {len(response_documents)} repository file(s) across "
            f"{', '.join(project_types) or 'unknown'} stack(s)."
        ),
    }


def search_repo_rag(
    *,
    root: str,
    query: str,
    pinned_paths: list[str] | tuple[str, ...] | None = None,
    changed_paths: list[str] | tuple[str, ...] | None = None,
    max_results: int = 12,
    max_scan_files: int = 5000,
    max_file_bytes: int = 120000,
    snippet_chars: int = 700,
) -> dict[str, Any]:
    if not query.strip():
        raise RepoContextError("Repo RAG search query is required.")
    if max_results < 1:
        raise RepoContextError("Repo RAG search max_results must be at least 1.")

    documents, skipped, scanned_count = _scan_documents(
        root=root,
        max_scan_files=max_scan_files,
        max_file_bytes=max_file_bytes,
    )
    root_path = Path(root).resolve()
    pinned = _validated_path_set(pinned_paths or (), root_path)
    changed = _validated_path_set(changed_paths or (), root_path)
    related_tests = _related_tests_for_changed(changed, documents)
    terms = _query_terms(query)

    scored: list[dict[str, Any]] = []
    for document in documents:
        score, matched_terms, reasons = _score_document(
            document,
            terms=terms,
            pinned=pinned,
            changed=changed,
            related_tests=related_tests,
            query=query,
        )
        if score <= 0:
            continue
        scored.append(
            {
                "path": document.path,
                "score": score,
                "kind": document.kind,
                "project_type": document.project_type,
                "matched_terms": matched_terms,
                "reasons": reasons,
                "symbols": list(document.symbols[:12]),
                "imports": list(document.imports[:8]),
                "snippet": _snippet(document.text_preview, terms, max_chars=snippet_chars),
            }
        )

    scored.sort(key=lambda item: (-int(item["score"]), str(item["path"])))
    results = scored[:max_results]
    selected_paths = [str(item["path"]) for item in results]
    index_id = _index_hash(documents)
    return {
        "source": "biber_repo_rag_search",
        "ok": bool(results),
        "index_version": INDEX_VERSION,
        "index_id": index_id,
        "query": query,
        "query_terms": terms,
        "selected_paths": selected_paths,
        "results": results,
        "index_summary": {
            "scanned_files": scanned_count,
            "indexed_files": len(documents),
            "skipped_files": len(skipped),
        },
        "skipped": skipped[:25],
        "summary": (
            f"Repo RAG selected {len(selected_paths)} file(s) for query terms: "
            f"{', '.join(terms) or 'none'}."
        ),
    }


def _scan_documents(
    *,
    root: str,
    max_scan_files: int,
    max_file_bytes: int,
) -> tuple[list[_IndexedDocument], list[dict[str, str]], int]:
    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise RepoContextError(f"Repo RAG root is not a directory: {root_path}")

    documents: list[_IndexedDocument] = []
    skipped: list[dict[str, str]] = []
    scanned_files = _iter_repo_files(root_path, max_scan_files=max_scan_files)
    for relative in scanned_files:
        if not _is_plan_candidate_file(relative):
            skipped.append({"path": relative.as_posix(), "reason": "not_indexable"})
            continue
        candidate = root_path / relative
        try:
            document = _index_document(candidate, root_path, max_file_bytes=max_file_bytes)
        except RepoContextError as exc:
            skipped.append({"path": relative.as_posix(), "reason": str(exc)})
            continue
        documents.append(document)
    return documents, skipped, len(scanned_files)


def _index_document(
    candidate: Path,
    root_path: Path,
    *,
    max_file_bytes: int,
) -> _IndexedDocument:
    size_bytes = candidate.stat().st_size
    read_size = min(size_bytes, max_file_bytes)
    data = candidate.read_bytes()[:read_size]
    if b"\x00" in data:
        raise RepoContextError("binary_file")
    text_preview = data.decode("utf-8", errors="replace")
    relative = candidate.relative_to(root_path)
    content_terms = _term_counts(text_preview)
    project_type = _project_type_for_path(relative) or _project_type_for_source(relative)
    return _IndexedDocument(
        path=relative.as_posix(),
        kind=_document_kind(relative),
        project_type=project_type,
        size_bytes=size_bytes,
        line_count=text_preview.count("\n") + (1 if text_preview else 0),
        sha256=sha256(data).hexdigest(),
        symbols=tuple(_extract_symbols(text_preview)),
        imports=tuple(_extract_imports(text_preview)),
        content_terms=content_terms,
        text_preview=text_preview,
    )


def _document_response(document: _IndexedDocument) -> dict[str, Any]:
    return {
        "path": document.path,
        "kind": document.kind,
        "project_type": document.project_type,
        "size_bytes": document.size_bytes,
        "line_count": document.line_count,
        "sha256": document.sha256,
        "symbols": list(document.symbols[:20]),
        "imports": list(document.imports[:12]),
        "term_count": sum(document.content_terms.values()),
    }


def _document_kind(path: Path) -> str:
    if _is_manifest_file(path):
        return "manifest"
    if _looks_like_test_path(path):
        return "test"
    if path.name.lower().startswith("readme") or path.suffix.lower() == ".md":
        return "documentation"
    if path.suffix.lower() in {".json", ".toml", ".yaml", ".yml", ".xml"}:
        return "configuration"
    return "source"


def _query_terms(value: str) -> list[str]:
    terms = []
    seen: set[str] = set()
    for term in re.findall(r"[A-Za-z0-9]{2,}", value.replace("_", " ").lower()):
        if term in _STOPWORDS or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms[:40]


def _term_counts(value: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for term in _query_terms(value):
        counts[term] = counts.get(term, 0) + 1
    return counts


def _extract_symbols(value: str) -> list[str]:
    patterns = [
        r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*(?:pub\s+)?(?:struct|enum|trait)\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\b(?:class|interface|record|struct|enum)\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bCREATE\s+(?:TABLE|VIEW|FUNCTION|PROCEDURE)\s+([A-Za-z0-9_.\"]+)",
    ]
    symbols: list[str] = []
    seen: set[str] = set()
    for line in value.splitlines():
        for pattern in patterns:
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if not match:
                continue
            symbol = match.group(1).strip('"')
            key = symbol.lower()
            if key in seen:
                continue
            seen.add(key)
            symbols.append(symbol)
            if len(symbols) >= 30:
                return symbols
    return symbols


def _extract_imports(value: str) -> list[str]:
    imports: list[str] = []
    seen: set[str] = set()
    for line in value.splitlines():
        stripped = line.strip()
        if not re.match(
            r"^(from\s+\S+\s+import|import\s+\S+|use\s+\S+|using\s+\S+|package\s+\S+|const\s+\S+\s*=\s*require\()",
            stripped,
        ):
            continue
        clean = stripped[:160]
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        imports.append(clean)
        if len(imports) >= 20:
            break
    return imports


def _validated_path_set(paths: list[str] | tuple[str, ...], root_path: Path) -> set[str]:
    results: set[str] = set()
    for raw_path in paths:
        candidate = _resolve_requested_path(raw_path, root_path)
        results.add(candidate.relative_to(root_path).as_posix())
    return results


def _related_tests_for_changed(
    changed: set[str],
    documents: list[_IndexedDocument],
) -> set[str]:
    scanned_paths = [Path(document.path) for document in documents]
    related: set[str] = set()
    for raw_path in changed:
        related.update(path.as_posix() for path in _related_test_paths(Path(raw_path), scanned_paths))
    return related


def _score_document(
    document: _IndexedDocument,
    *,
    terms: list[str],
    pinned: set[str],
    changed: set[str],
    related_tests: set[str],
    query: str,
) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons: list[str] = []
    matched_terms: list[str] = []
    path_text = document.path.lower()
    symbol_text = " ".join(document.symbols).lower()
    import_text = " ".join(document.imports).lower()

    if document.path in pinned:
        score += 160
        reasons.append("pinned_path")
    if document.path in changed:
        score += 140
        reasons.append("changed_path")
    if document.path in related_tests:
        score += 45
        reasons.append("related_test")

    for term in terms:
        term_score = 0
        if term in path_text:
            term_score += 16
        if term in symbol_text:
            term_score += 14
        if term in import_text:
            term_score += 5
        term_score += min(document.content_terms.get(term, 0), 8) * 3
        if term_score:
            matched_terms.append(term)
            score += term_score

    lowered_query = query.lower()
    if "test" in lowered_query or "fail" in lowered_query or "diagnos" in lowered_query:
        if document.kind == "test":
            score += 18
            reasons.append("test_intent")
    if "readme" in lowered_query or "doc" in lowered_query or "architecture" in lowered_query:
        if document.kind == "documentation":
            score += 12
            reasons.append("documentation_intent")
    if document.kind == "manifest":
        score += 7
        reasons.append("manifest_context")

    if matched_terms and not reasons:
        reasons.append("lexical_match")
    return score, sorted(set(matched_terms)), reasons


def _snippet(value: str, terms: list[str], *, max_chars: int) -> str:
    if not value:
        return ""
    lowered = value.lower()
    indexes = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    start = max(0, (min(indexes) - 220) if indexes else 0)
    end = min(len(value), start + max_chars)
    snippet = value[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(value):
        snippet += "..."
    return _redact_secret_lines(snippet)


def _redact_secret_lines(value: str) -> str:
    lines = []
    for line in value.splitlines():
        if _SECRET_LINE_RE.search(line):
            lines.append("[redacted secret-like line]")
        else:
            lines.append(line)
    return "\n".join(lines)


def _index_hash(documents: list[_IndexedDocument]) -> str:
    payload = "|".join(
        f"{document.path}:{document.sha256}:{document.size_bytes}"
        for document in sorted(documents, key=lambda item: item.path)
    )
    return sha256(payload.encode("utf-8")).hexdigest()
