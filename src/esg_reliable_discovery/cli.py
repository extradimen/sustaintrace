from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from .archive import RunArchive, build_model_manifest
from .blinding import build_blind_pool_paths
from .config import ModelConfig
from .ingest import ingest_document, verify_document
from .knowledge_query import query_control_plane, query_facts, query_repair_lifecycle
from .manifest import lock_manifest, summarize_manifest_path
from .mineru_adapter import parse_with_mineru, probe_mineru
from .ollama_client import OllamaClient
from .open_review import compare_review_paths
from .p1_annotation import compare_p1_annotation_paths
from .p1_gates import audit_p1_gates
from .p1_sampling import sample_p1_sources
from .p1_task_gate import audit_p1_task_exposure
from .p1_tasks import allocate_p1_task_slots
from .parser_scoring import score_parser_benchmark
from .prompt_guard import audit_prompt_paths
from .run_scoring import score_archived_closed_run
from .run_scoring_v2 import score_archived_closed_run_v2
from .scoring import score_finding_card_paths
from .structured_output import parse_strict_json_content
from .task_runner import run_task


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def command_query_facts(args: argparse.Namespace) -> None:
    _print(
        query_facts(
            args.knowledge_base_directory,
            task_id=args.task_id,
            document_id=args.document_id,
            company=args.company,
            predicate=args.predicate,
            include_candidates=args.include_candidates,
            limit=args.limit,
            offset=args.offset,
        )
    )


def command_query_repairs(args: argparse.Namespace) -> None:
    _print(
        query_repair_lifecycle(
            args.knowledge_base_directory,
            args.strategy_catalog,
            execution_id=args.execution_id,
            state=args.state,
            failure_signature=args.failure_signature,
            include_regression_observations=args.include_regression_observations,
        )
    )


def command_query_control_plane(args: argparse.Namespace) -> None:
    _print(
        query_control_plane(
            args.knowledge_base_directory,
            args.strategy_catalog,
            include_candidates=args.include_candidates,
            include_regression_observations=args.include_regression_observations,
        )
    )


def command_probe(args: argparse.Namespace) -> None:
    config = ModelConfig.from_path(args.config)
    client = OllamaClient(config)
    models = client.list_models()
    digest = client.verify_digest()
    details = client.show_model()
    _print({"config": config.public_dict(), "digest": digest, "details": details, "models": models})


def command_chat(args: argparse.Namespace) -> None:
    config = ModelConfig.from_path(args.config)
    client = OllamaClient(config)
    schema = None
    if args.schema:
        schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    digest = client.verify_digest()
    details = client.show_model()
    result = client.chat(
        [{"role": "user", "content": args.prompt}], schema=schema, think=args.think
    )
    content = result.response.get("message", {}).get("content")
    normalized = None
    parse_error = None
    if schema and isinstance(content, str):
        try:
            normalized = parse_strict_json_content(content)
        except json.JSONDecodeError as error:
            parse_error = error
    if args.archive_root and args.experiment_id and args.run_id:
        archive = RunArchive.create(args.archive_root, args.experiment_id, args.run_id)
        manifest = build_model_manifest(config.public_dict(), details, digest)
        additional_json = None
        if parse_error is not None:
            additional_json = {
                "failure.json": {
                    "stage": "structured_response_parse",
                    "error_type": type(parse_error).__name__,
                    "error_message": str(parse_error),
                    "model_output_received": True,
                    "posthoc_model_output_repair_applied": False,
                }
            }
        archive.record_result(
            result,
            model_manifest=manifest,
            normalized_output=normalized,
            additional_json=additional_json,
        )
    if parse_error is not None:
        raise parse_error
    _print({"content": content, "elapsed_seconds": result.elapsed_seconds, "digest": digest})


def command_ingest_document(args: argparse.Namespace) -> None:
    _print(ingest_document(args.manifest, args.document_id, args.raw_root))


def command_verify_document(args: argparse.Namespace) -> None:
    pages = [int(value) for value in args.representative_pages.split(",")]
    _print(
        verify_document(
            args.manifest,
            args.document_id,
            args.raw_root,
            representative_pages=pages,
            visual_review=args.visual_review,
        )
    )


def command_mineru_probe(args: argparse.Namespace) -> None:
    _print(probe_mineru(args.executable))


def command_mineru_parse(args: argparse.Namespace) -> None:
    _print(
        parse_with_mineru(
            args.input_pdf,
            args.output_directory,
            executable=args.executable,
            backend=args.backend,
            method=args.method,
            start_page=args.start_page,
            end_page=args.end_page,
            tools_config=args.tools_config,
            timeout_seconds=args.timeout_seconds,
        )
    )


def command_manifest_summary(args: argparse.Namespace) -> None:
    _print(summarize_manifest_path(args.manifest))


def command_manifest_lock(args: argparse.Namespace) -> None:
    _print(
        lock_manifest(
            args.manifest,
            args.raw_root,
            args.lock_file,
            minimum_verified=args.minimum_verified,
        )
    )


def command_score_card(args: argparse.Namespace) -> None:
    _print(score_finding_card_paths(args.candidate, args.gold, args.schema))


def command_compare_open_reviews(args: argparse.Namespace) -> None:
    _print(compare_review_paths(args.reviews_a, args.reviews_b, args.schema))


def command_audit_prompt(args: argparse.Namespace) -> None:
    result = audit_prompt_paths(args.prompt, args.gold_directory)
    _print(result)
    if not result["passed"]:
        raise SystemExit(1)


def command_build_blind_pool(args: argparse.Namespace) -> None:
    _print(
        build_blind_pool_paths(
            args.candidate,
            pool_id=args.pool_id,
            task_id=args.task_id,
            seed=args.seed,
            output_directory=args.output_directory,
            identity_map_path=args.identity_map,
            schema_path=args.schema,
        )
    )


def command_run_task(args: argparse.Namespace) -> None:
    _print(
        run_task(
            model_config_path=args.config,
            task_pack_path=args.task_pack,
            task_id=args.task_id,
            document_manifest_path=args.document_manifest,
            raw_root=args.raw_root,
            system_prompt_path=args.system_prompt,
            finding_schema_path=args.schema,
            archive_root=args.archive_root,
            experiment_id=args.experiment_id,
            run_id=args.run_id,
            framework_version=args.framework_version,
            include_images=args.include_images,
            think=args.think,
            injection_policy_path=args.injection_policy,
            task_contracts_path=args.task_contracts,
            evidence_handle_policy_path=args.evidence_handle_policy,
            calculation_policy_path=args.calculation_policy,
        )
    )


def command_score_run(args: argparse.Namespace) -> None:
    _print(score_archived_closed_run(args.run_directory, args.gold_directory, args.schema))


def command_score_run_v2(args: argparse.Namespace) -> None:
    _print(score_archived_closed_run_v2(args.run_directory, args.gold_directory, args.schema))


def command_score_parser(args: argparse.Namespace) -> None:
    _print(score_parser_benchmark(args.spec, args.repository_root))


def command_audit_p1(args: argparse.Namespace) -> None:
    result = audit_p1_gates(args.plan, args.registry, args.acquisition_manifest)
    _print(result)
    if not result["gate_state_consistent"]:
        raise SystemExit(2)


def command_sample_p1(args: argparse.Namespace) -> None:
    result = sample_p1_sources(
        args.registry,
        seed=args.seed,
        per_stratum=args.per_stratum,
        minimum_per_region=args.minimum_per_region,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent, prefix=f".{output.name}.", delete=False
        ) as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            temporary = Path(stream.name)
        os.replace(temporary, output)
    _print(result)


def command_allocate_p1_tasks(args: argparse.Namespace) -> None:
    quotas = json.loads(Path(args.quotas).read_text(encoding="utf-8"))
    result = allocate_p1_task_slots(args.sample_manifest, quotas, seed=args.seed)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent, prefix=f".{output.name}.", delete=False
        ) as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            temporary = Path(stream.name)
        os.replace(temporary, output)
    _print(result)


def command_compare_p1_annotations(args: argparse.Namespace) -> None:
    _print(compare_p1_annotation_paths(args.annotation_a, args.annotation_b, args.schema))


def command_audit_p1_task_exposure(args: argparse.Namespace) -> None:
    result = audit_p1_task_exposure(args.task_pack, args.exclusion_lock)
    _print(result)
    if not result["passed"]:
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="esg-rd")
    subparsers = parser.add_subparsers(dest="command", required=True)

    query_facts_parser = subparsers.add_parser(
        "query-facts",
        help="Query trusted facts; candidates require an explicit opt-in and retain all gaps",
    )
    query_facts_parser.add_argument(
        "--knowledge-base-directory", default="data/knowledge_bases/v0.1"
    )
    query_facts_parser.add_argument("--task-id")
    query_facts_parser.add_argument("--document-id")
    query_facts_parser.add_argument("--company")
    query_facts_parser.add_argument("--predicate")
    query_facts_parser.add_argument("--include-candidates", action="store_true")
    query_facts_parser.add_argument("--limit", type=int, default=100)
    query_facts_parser.add_argument("--offset", type=int, default=0)
    query_facts_parser.set_defaults(func=command_query_facts)

    query_repairs_parser = subparsers.add_parser(
        "query-repairs",
        help="Query failure, repair-plan, validation, execution and rollback lineage",
    )
    query_repairs_parser.add_argument(
        "--knowledge-base-directory", default="data/knowledge_bases/v0.1"
    )
    query_repairs_parser.add_argument(
        "--strategy-catalog", default="configs/knowledge/repair_strategy_catalog_v0.1.json"
    )
    query_repairs_parser.add_argument("--execution-id")
    query_repairs_parser.add_argument("--state")
    query_repairs_parser.add_argument("--failure-signature")
    query_repairs_parser.add_argument("--include-regression-observations", action="store_true")
    query_repairs_parser.set_defaults(func=command_query_repairs)

    control_plane_parser = subparsers.add_parser(
        "query-control-plane",
        help="Query both fact knowledge and failure-repair knowledge under one trust policy",
    )
    control_plane_parser.add_argument(
        "--knowledge-base-directory", default="data/knowledge_bases/v0.1"
    )
    control_plane_parser.add_argument(
        "--strategy-catalog", default="configs/knowledge/repair_strategy_catalog_v0.1.json"
    )
    control_plane_parser.add_argument("--include-candidates", action="store_true")
    control_plane_parser.add_argument("--include-regression-observations", action="store_true")
    control_plane_parser.set_defaults(func=command_query_control_plane)

    probe = subparsers.add_parser("probe", help="Capture model and endpoint metadata")
    probe.add_argument("--config", required=True)
    probe.set_defaults(func=command_probe)

    chat = subparsers.add_parser("chat", help="Run and optionally archive one chat request")
    chat.add_argument("--config", required=True)
    chat.add_argument("--prompt", required=True)
    chat.add_argument("--schema")
    chat.add_argument("--think", action=argparse.BooleanOptionalAction, default=None)
    chat.add_argument("--archive-root")
    chat.add_argument("--experiment-id")
    chat.add_argument("--run-id")
    chat.set_defaults(func=command_chat)

    ingest = subparsers.add_parser("ingest-document", help="Download and register one manifest PDF")
    ingest.add_argument("--manifest", required=True)
    ingest.add_argument("--document-id", required=True)
    ingest.add_argument("--raw-root", default="data/raw")
    ingest.set_defaults(func=command_ingest_document)

    verify = subparsers.add_parser(
        "verify-document", help="Verify hash, PDF structure, text layer, and visual QA"
    )
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--document-id", required=True)
    verify.add_argument("--raw-root", default="data/raw")
    verify.add_argument("--representative-pages", required=True)
    verify.add_argument("--visual-review", choices=["passed", "failed"], required=True)
    verify.set_defaults(func=command_verify_document)

    mineru_probe = subparsers.add_parser("mineru-probe", help="Report locked MinerU availability")
    mineru_probe.add_argument("--executable", default="mineru")
    mineru_probe.set_defaults(func=command_mineru_probe)

    mineru_parse = subparsers.add_parser(
        "mineru-parse", help="Parse one PDF with MinerU and archive parser provenance"
    )
    mineru_parse.add_argument("--input-pdf", required=True)
    mineru_parse.add_argument("--output-directory", required=True)
    mineru_parse.add_argument("--executable", default="mineru")
    mineru_parse.add_argument("--backend", default="pipeline")
    mineru_parse.add_argument("--method", default="auto")
    mineru_parse.add_argument("--start-page", type=int)
    mineru_parse.add_argument("--end-page", type=int)
    mineru_parse.add_argument("--tools-config")
    mineru_parse.add_argument("--timeout-seconds", type=int, default=7200)
    mineru_parse.set_defaults(func=command_mineru_parse)

    summary = subparsers.add_parser(
        "manifest-summary", help="Summarize document status and verified sample coverage"
    )
    summary.add_argument("--manifest", required=True)
    summary.set_defaults(func=command_manifest_summary)

    lock = subparsers.add_parser(
        "manifest-lock", help="Verify source hashes and freeze a completed document manifest"
    )
    lock.add_argument("--manifest", required=True)
    lock.add_argument("--raw-root", default="data/raw")
    lock.add_argument("--lock-file", required=True)
    lock.add_argument("--minimum-verified", type=int, default=10)
    lock.set_defaults(func=command_manifest_lock)

    score = subparsers.add_parser(
        "score-card", help="Score one candidate finding card without an aggregate score"
    )
    score.add_argument("--candidate", required=True)
    score.add_argument("--gold", required=True)
    score.add_argument("--schema", default="templates/finding_card.schema.json")
    score.set_defaults(func=command_score_card)

    compare_reviews = subparsers.add_parser(
        "compare-open-reviews",
        help="Report dimension-wise agreement and open-discovery adjudication queue",
    )
    compare_reviews.add_argument("--reviews-a", required=True)
    compare_reviews.add_argument("--reviews-b", required=True)
    compare_reviews.add_argument("--schema", default="templates/open_discovery_review.schema.json")
    compare_reviews.set_defaults(func=command_compare_open_reviews)

    audit_prompt = subparsers.add_parser(
        "audit-prompt", help="Detect closed-task answer leakage in instruction text"
    )
    audit_prompt.add_argument("--prompt", required=True)
    audit_prompt.add_argument("--gold-directory", default="data/annotations/p0_gold")
    audit_prompt.set_defaults(func=command_audit_prompt)

    blind_pool = subparsers.add_parser(
        "build-blind-pool", help="Anonymize and deterministically randomize finding cards"
    )
    blind_pool.add_argument("--candidate", action="append", required=True)
    blind_pool.add_argument("--pool-id", required=True)
    blind_pool.add_argument("--task-id", required=True)
    blind_pool.add_argument("--seed", type=int, required=True)
    blind_pool.add_argument("--output-directory", required=True)
    blind_pool.add_argument("--identity-map", required=True)
    blind_pool.add_argument("--schema", default="templates/finding_card.schema.json")
    blind_pool.set_defaults(func=command_build_blind_pool)

    task_run = subparsers.add_parser(
        "run-task", help="Run one locked model on one P0 task and archive a redacted request"
    )
    task_run.add_argument("--config", required=True)
    task_run.add_argument("--task-pack", default="data/tasks/p0_task_pack_v0.1.json")
    task_run.add_argument("--task-id", required=True)
    task_run.add_argument("--document-manifest", default="data/manifests/p0_manifest.json")
    task_run.add_argument("--raw-root", default="data/raw")
    task_run.add_argument("--system-prompt", default="prompts/p0_evidence_discovery_v0.1.txt")
    task_run.add_argument("--schema", default="templates/finding_card.schema.json")
    task_run.add_argument("--archive-root", default="research_archive/experiments")
    task_run.add_argument("--experiment-id", required=True)
    task_run.add_argument("--run-id", required=True)
    task_run.add_argument("--framework-version", default="V0")
    task_run.add_argument("--include-images", action=argparse.BooleanOptionalAction, default=False)
    task_run.add_argument("--think", action=argparse.BooleanOptionalAction, default=None)
    task_run.add_argument(
        "--injection-policy",
        help="Pre-registered deterministic framework-field injection policy",
    )
    task_run.add_argument(
        "--task-contracts",
        help="Pre-registered task-type-conditioned model-output contracts",
    )
    task_run.add_argument("--evidence-handle-policy")
    task_run.add_argument("--calculation-policy")
    task_run.set_defaults(func=command_run_task)

    score_run = subparsers.add_parser(
        "score-run", help="Verify and score one immutable closed-task run archive"
    )
    score_run.add_argument("--run-directory", required=True)
    score_run.add_argument("--gold-directory", default="data/annotations/p0_gold")
    score_run.add_argument("--schema", default="templates/finding_card.schema.json")
    score_run.set_defaults(func=command_score_run)
    score_run_v2 = subparsers.add_parser(
        "score-run-v2",
        help="Add non-aggregate field-wise diagnostic scores to a closed-task archive",
    )
    score_run_v2.add_argument("--run-directory", required=True)
    score_run_v2.add_argument("--gold-directory", default="data/annotations/p0_gold")
    score_run_v2.add_argument("--schema", default="templates/finding_card.schema.json")
    score_run_v2.set_defaults(func=command_score_run_v2)
    score_parser = subparsers.add_parser(
        "score-parser", help="Score archived parser outputs against atomic assertions"
    )
    score_parser.add_argument("--spec", required=True)
    score_parser.add_argument("--repository-root", default=".")
    score_parser.set_defaults(func=command_score_parser)

    audit_p1 = subparsers.add_parser(
        "audit-p1-gates", help="Audit P1 source readiness and inference safety gates"
    )
    audit_p1.add_argument("--plan", required=True)
    audit_p1.add_argument("--registry", required=True)
    audit_p1.add_argument("--acquisition-manifest")
    audit_p1.set_defaults(func=command_audit_p1)

    sample_p1 = subparsers.add_parser(
        "sample-p1-sources", help="Deterministically sample a frozen P1 source registry"
    )
    sample_p1.add_argument("--registry", required=True)
    sample_p1.add_argument("--seed", required=True, type=int)
    sample_p1.add_argument("--per-stratum", type=int, default=4)
    sample_p1.add_argument("--minimum-per-region", type=int, default=3)
    sample_p1.add_argument("--output")
    sample_p1.set_defaults(func=command_sample_p1)

    allocate_tasks = subparsers.add_parser(
        "allocate-p1-task-slots", help="Allocate frozen P1 task-type slots without answers"
    )
    allocate_tasks.add_argument("--sample-manifest", required=True)
    allocate_tasks.add_argument("--quotas", required=True)
    allocate_tasks.add_argument("--seed", required=True, type=int)
    allocate_tasks.add_argument("--output")
    allocate_tasks.set_defaults(func=command_allocate_p1_tasks)

    compare_p1 = subparsers.add_parser(
        "compare-p1-annotations",
        help="Validate two independent P1 annotations and emit a field-level adjudication queue",
    )
    compare_p1.add_argument("--annotation-a", required=True)
    compare_p1.add_argument("--annotation-b", required=True)
    compare_p1.add_argument("--schema", default="templates/p1_annotation.schema.json")
    compare_p1.set_defaults(func=command_compare_p1_annotations)

    task_exposure = subparsers.add_parser(
        "audit-p1-task-exposure",
        help="Reject incomplete P1 tasks and any eligibility-QA page reused as target evidence",
    )
    task_exposure.add_argument("--task-pack", required=True)
    task_exposure.add_argument(
        "--exclusion-lock",
        default="data/manifests/p1_eligibility_exposure_exclusions.lock.json",
    )
    task_exposure.set_defaults(func=command_audit_p1_task_exposure)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
