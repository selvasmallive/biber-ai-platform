from __future__ import annotations

from pathlib import Path

from biber_api.repo_rag import build_repo_rag_index, search_repo_rag


def test_repo_rag_indexes_allowed_files_and_skips_generated_dirs(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\nWallet service\n", encoding="utf-8")
    source = tmp_path / "src" / "wallet.py"
    source.parent.mkdir()
    source.write_text(
        "from decimal import Decimal\n\n"
        "class WalletService:\n"
        "    def send_payment(self, amount: Decimal) -> str:\n"
        "        return 'ok'\n",
        encoding="utf-8",
    )
    generated = tmp_path / "node_modules" / "pkg" / "index.js"
    generated.parent.mkdir(parents=True)
    generated.write_text("console.log('ignored')\n", encoding="utf-8")

    index = build_repo_rag_index(root=str(tmp_path))

    assert index["ok"] is True
    paths = {document["path"] for document in index["documents"]}
    assert "README.md" in paths
    assert "src/wallet.py" in paths
    assert "node_modules/pkg/index.js" not in paths
    wallet = next(document for document in index["documents"] if document["path"] == "src/wallet.py")
    assert wallet["kind"] == "source"
    assert wallet["project_type"] == "python"
    assert "WalletService" in wallet["symbols"]
    assert "send_payment" in wallet["symbols"]
    assert wallet["imports"] == ["from decimal import Decimal"]


def test_repo_rag_search_prioritizes_changed_file_related_test_and_manifest(
    tmp_path: Path,
) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"test":"vitest"}}\n', encoding="utf-8")
    component = tmp_path / "src" / "components" / "WalletButton.tsx"
    component.parent.mkdir(parents=True)
    component.write_text(
        "export function WalletButton() {\n"
        "  return <button disabled={false}>Send</button>\n"
        "}\n",
        encoding="utf-8",
    )
    test = tmp_path / "src" / "components" / "WalletButton.test.tsx"
    test.write_text("test('disables send button', () => {})\n", encoding="utf-8")

    result = search_repo_rag(
        root=str(tmp_path),
        query="Fix WalletButton disabled send behavior and tests",
        changed_paths=["src/components/WalletButton.tsx"],
        max_results=5,
    )

    assert result["ok"] is True
    assert result["selected_paths"][0] == "src/components/WalletButton.tsx"
    assert "src/components/WalletButton.test.tsx" in result["selected_paths"]
    assert "package.json" in result["selected_paths"]
    reasons = {
        item["path"]: item["reasons"]
        for item in result["results"]
    }
    assert "changed_path" in reasons["src/components/WalletButton.tsx"]
    assert "related_test" in reasons["src/components/WalletButton.test.tsx"]
    assert "manifest_context" in reasons["package.json"]


def test_repo_rag_search_redacts_secret_like_snippet_lines(tmp_path: Path) -> None:
    source = tmp_path / "src" / "settings.py"
    source.parent.mkdir()
    source.write_text(
        "API_KEY = 'do-not-show'\n"
        "def configure_api_key() -> str:\n"
        "    return 'configured'\n",
        encoding="utf-8",
    )

    result = search_repo_rag(
        root=str(tmp_path),
        query="api key configuration",
        max_results=3,
    )

    assert result["selected_paths"] == ["src/settings.py"]
    snippet = result["results"][0]["snippet"]
    assert "[redacted secret-like line]" in snippet
    assert "do-not-show" not in snippet
