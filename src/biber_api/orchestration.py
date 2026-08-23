from __future__ import annotations

from typing import Any

from .config import BiberSettings
from .repo_context import RepoContextError, plan_repo_context
from .repo_rag import search_repo_rag
from .test_runner import UnknownTestCommandError, list_test_commands
from .workspace_edit import WorkspaceEditError, plan_workspace_edits


ORCHESTRATION_VERSION = "agent-orchestration-plan-v1"


def plan_agent_orchestration(
    *,
    settings: BiberSettings,
    instruction: str,
    pinned_paths: list[str] | tuple[str, ...] | None = None,
    changed_paths: list[str] | tuple[str, ...] | None = None,
    proposed_edits: list[dict[str, Any]] | None = None,
    test_id: str | None = None,
    max_context_files: int = 12,
    max_rag_results: int = 12,
    max_scan_files: int = 5000,
) -> dict[str, Any]:
    if not instruction.strip():
        raise RepoContextError("Agent orchestration instruction is required.")

    pinned = list(pinned_paths or [])
    changed = list(changed_paths or [])
    rag = search_repo_rag(
        root=settings.repo_context_root,
        query=instruction,
        pinned_paths=pinned,
        changed_paths=changed,
        max_results=max_rag_results,
        max_scan_files=max_scan_files,
    )
    retrieved_paths = [str(path) for path in rag.get("selected_paths", [])]
    context_pins = _dedupe_paths([*pinned, *retrieved_paths])[:max_context_files]
    context_plan = plan_repo_context(
        root=settings.repo_context_root,
        instruction=instruction,
        pinned_paths=context_pins,
        changed_paths=changed,
        max_files=min(max_context_files, settings.repo_context_max_files),
        max_scan_files=max_scan_files,
    )

    edit_plan: dict[str, Any] | None = None
    edit_status = "not_requested"
    if proposed_edits:
        try:
            edit_plan = plan_workspace_edits(
                edits=proposed_edits,
                settings=settings,
                max_files=min(len(proposed_edits), 8),
            )
            edit_status = "planned" if edit_plan.get("ok") else "blocked"
        except WorkspaceEditError as exc:
            edit_plan = {
                "ok": False,
                "plan_hash": None,
                "planned": [],
                "rejected": [{"path": "<proposed_edits>", "error": str(exc)}],
                "files_touched": 0,
                "total_new_bytes": 0,
                "summary": str(exc),
            }
            edit_status = "blocked"

    test_plan = _test_plan(settings, test_id)
    gates = _required_gates(
        edit_plan=edit_plan,
        test_id=test_id,
    )
    agents = _agent_roles()
    workflow_steps = _workflow_steps(
        rag=rag,
        context_plan=context_plan,
        edit_status=edit_status,
        test_plan=test_plan,
    )
    hard_blockers = _hard_blockers(edit_plan=edit_plan, test_plan=test_plan)
    ok = not hard_blockers

    return {
        "source": "biber_agent_orchestration_plan",
        "ok": ok,
        "orchestration_version": ORCHESTRATION_VERSION,
        "instruction": instruction,
        "agents": agents,
        "workflow_steps": workflow_steps,
        "repo_rag": rag,
        "repo_context": context_plan,
        "edit_plan": edit_plan,
        "test_plan": test_plan,
        "required_gates": gates,
        "hard_blockers": hard_blockers,
        "safe_to_apply": False,
        "mentor_required": False,
        "mentor_optional": True,
        "next_actions": _next_actions(
            edit_plan=edit_plan,
            test_plan=test_plan,
            context_plan=context_plan,
        ),
        "summary": (
            "Planned BIBER repo-RAG, context, edit, test, and review workflow; "
            "no model call, file mutation, GitHub save, training, or OpenAI mentor call was performed."
        ),
    }


def _dedupe_paths(paths: list[str]) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for path in paths:
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(path)
    return selected


def _agent_roles() -> list[dict[str, Any]]:
    return [
        {
            "id": "planner",
            "responsibility": "Turn the user instruction into a narrow implementation objective.",
            "mutation_allowed": False,
        },
        {
            "id": "repo_retriever",
            "responsibility": "Search the full allowed repository index and select bounded context files.",
            "mutation_allowed": False,
        },
        {
            "id": "coder",
            "responsibility": "Produce strict proposed edits only after context is selected.",
            "mutation_allowed": False,
        },
        {
            "id": "edit_guard",
            "responsibility": "Validate proposed multi-file edits with dry-run hashes before apply.",
            "mutation_allowed": False,
        },
        {
            "id": "test_diagnoser",
            "responsibility": "Run the narrow configured test and diagnose failures before another edit loop.",
            "mutation_allowed": False,
        },
        {
            "id": "reviewer",
            "responsibility": "Request human or optional mentor review for risky changes.",
            "mutation_allowed": False,
        },
        {
            "id": "git_saver",
            "responsibility": "Save or PR only after explicit GitHub action is requested.",
            "mutation_allowed": False,
        },
    ]


def _workflow_steps(
    *,
    rag: dict[str, Any],
    context_plan: dict[str, Any],
    edit_status: str,
    test_plan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    return [
        {
            "name": "repo_rag_search",
            "agent": "repo_retriever",
            "status": "ok" if rag.get("ok") else "needs_more_context",
            "output_keys": ["selected_paths", "results", "index_summary"],
        },
        {
            "name": "repo_context_plan",
            "agent": "repo_retriever",
            "status": "ok" if context_plan.get("selected_paths") else "needs_more_context",
            "selected_paths": context_plan.get("selected_paths", []),
        },
        {
            "name": "model_edit_proposal",
            "agent": "coder",
            "status": "next",
            "contract": "strict JSON edits; no direct file mutation",
        },
        {
            "name": "workspace_edit_plan",
            "agent": "edit_guard",
            "status": edit_status,
            "contract": "dry-run first; apply only with matching plan_hash",
        },
        {
            "name": "test_and_diagnose",
            "agent": "test_diagnoser",
            "status": "planned" if test_plan else "not_requested",
            "test_id": test_plan.get("test_id") if test_plan else None,
        },
    ]


def _test_plan(settings: BiberSettings, test_id: str | None) -> dict[str, Any] | None:
    if not test_id:
        return None
    for command in list_test_commands(settings):
        if command.get("test_id") == test_id:
            return {
                "ok": True,
                "test_id": test_id,
                "command": command,
                "diagnosis_on_failure": True,
            }
    raise UnknownTestCommandError(f"Unknown test_id: {test_id}")


def _required_gates(
    *,
    edit_plan: dict[str, Any] | None,
    test_id: str | None,
) -> list[str]:
    gates = [
        "bounded_repo_context_before_model_edit",
        "no_secret_paths_in_context_or_edits",
    ]
    if edit_plan is not None:
        gates.extend(
            [
                "human_review_edit_plan",
                "matching_plan_hash_before_apply",
                "rollback_on_apply_error",
            ]
        )
    if test_id:
        gates.extend(
            [
                "run_configured_test_after_apply",
                "diagnose_failure_before_next_repair_loop",
            ]
        )
    gates.extend(
        [
            "github_save_or_pr_only_when_explicitly_requested",
            "openai_mentor_optional_and_disabled_by_default",
        ]
    )
    return gates


def _hard_blockers(
    *,
    edit_plan: dict[str, Any] | None,
    test_plan: dict[str, Any] | None,
) -> list[str]:
    blockers: list[str] = []
    if edit_plan is not None and not edit_plan.get("ok"):
        blockers.append("edit_plan_blocked")
    if test_plan is not None and not test_plan.get("ok"):
        blockers.append("test_plan_blocked")
    return blockers


def _next_actions(
    *,
    edit_plan: dict[str, Any] | None,
    test_plan: dict[str, Any] | None,
    context_plan: dict[str, Any],
) -> list[str]:
    actions = [
        "Send the selected repo_context.selected_paths to the local model with a narrow edit request.",
        "Require the model to return strict JSON edits instead of free-form code blocks.",
    ]
    if edit_plan is None:
        actions.append("Run /v1/files/edit/plan on any proposed edits before applying.")
    elif edit_plan.get("ok"):
        actions.append("Review the edit plan and apply only with the matching plan_hash.")
    else:
        actions.append("Fix rejected edits before calling apply.")
    if test_plan:
        actions.append("Run the configured test after apply and diagnose failure output if needed.")
    if context_plan.get("selected_paths"):
        actions.append("Keep the next prompt bounded to the selected context paths.")
    return actions
