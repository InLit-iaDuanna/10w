"""Command-line interface for module validation, generation, and scaffolding."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Optional

from .activation import resolve_module_states
from .catalog import write_generated_files
from .diagnostics import RepositoryValidationError
from .repository import validate_repository
from .scaffold import ScaffoldError, scaffold_module


def _repository_root(value: str) -> Path:
    root = Path(value).resolve()
    if not (root / "modules").is_dir():
        raise argparse.ArgumentTypeError(f"not a SceneOps repository root: {root}")
    return root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sceneops-modules")
    parser.add_argument("--repo", type=_repository_root, default=Path.cwd())
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("validate", help="validate manifests, graph, entrypoints, and imports")

    generate = subcommands.add_parser("generate", help="generate static module catalogs")
    generate.add_argument("--check", action="store_true")

    scaffold = subcommands.add_parser("scaffold", help="create a minimal compliant module")
    scaffold.add_argument("module_id")
    scaffold.add_argument("--title", required=True)
    scaffold.add_argument("--description", required=True)
    scaffold.add_argument(
        "--surface", choices=("frontend", "backend", "both"), default="both"
    )
    scaffold.add_argument("--no-core-dependencies", action="store_true")

    states = subcommands.add_parser("states", help="resolve module availability metadata")
    states.add_argument("--disable", action="append", default=[], metavar="FEATURE_FLAG")
    states.add_argument("--integration", action="append", default=[], metavar="INTEGRATION_ID")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    repository_root = Path(args.repo).resolve()
    try:
        if args.command == "scaffold":
            surfaces = ("frontend", "backend") if args.surface == "both" else (args.surface,)
            target = scaffold_module(
                repository_root,
                args.module_id,
                args.title,
                args.description,
                surfaces=surfaces,
                include_core_dependencies=not args.no_core_dependencies,
            )
            print(f"Scaffolded {target.relative_to(repository_root)}")
            return 0

        graph = validate_repository(repository_root)
        if args.command == "validate":
            print(f"Validated {len(graph.sources)} modules: {', '.join(graph.module_ids)}")
            return 0
        if args.command == "generate":
            changed = write_generated_files(repository_root, graph, check=args.check)
            if args.check and changed:
                for path in changed:
                    print(
                        f"out of date: {path.relative_to(repository_root)}", file=sys.stderr
                    )
                return 1
            verb = "Checked" if args.check else "Generated"
            print(f"{verb} module catalogs for {len(graph.sources)} modules.")
            return 0
        if args.command == "states":
            flags = {flag: False for flag in args.disable}
            states = resolve_module_states(
                graph.manifests,
                feature_flags=flags,
                available_integrations=args.integration,
            )
            print(
                json.dumps(
                    {
                        module_id: state.model_dump(mode="json")
                        for module_id, state in states.items()
                    },
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
    except (RepositoryValidationError, ScaffoldError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.error(f"unsupported command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
