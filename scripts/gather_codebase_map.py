#!/usr/bin/env python3
"""
Codebase Map Gatherer - AST-based extraction of code elements.

This script parses the codebase using Python's ast module and TypeScript
tools to generate/update the codebase_map.json file.

Usage:
    python scripts/gather_codebase_map.py [--incremental] [--package PACKAGE]

Options:
    --incremental   Only update changed files since last run
    --package       Only process specific package (daw-agents, daw-frontend)
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Project root detection
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CODEBASE_MAP_PATH = PROJECT_ROOT / "docs" / "codebase_map.json"
SCHEMA_PATH = PROJECT_ROOT / "docs" / "codebase_map.schema.json"


@dataclass
class ClassInfo:
    """Extracted class information."""

    name: str
    line: int
    description: str = ""
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    methods: list[dict[str, Any]] = field(default_factory=list)
    properties: list[dict[str, Any]] = field(default_factory=list)
    class_variables: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FunctionInfo:
    """Extracted function information."""

    name: str
    line: int
    description: str = ""
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    return_type: str | None = None


@dataclass
class TypeInfo:
    """Extracted type/enum information."""

    name: str
    kind: str  # enum, type_alias, typed_dict, protocol, dataclass, pydantic_model
    line: int
    description: str = ""
    members: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ModuleInfo:
    """Extracted module information."""

    name: str
    path: str
    description: str = ""
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    types: list[TypeInfo] = field(default_factory=list)
    constants: list[dict[str, Any]] = field(default_factory=list)
    imports: list[dict[str, Any]] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)


class PythonASTExtractor(ast.NodeVisitor):
    """Extracts code elements from Python AST."""

    def __init__(self, source_code: str) -> None:
        self.source_code = source_code
        self.source_lines = source_code.split("\n")
        self.classes: list[ClassInfo] = []
        self.functions: list[FunctionInfo] = []
        self.types: list[TypeInfo] = []
        self.constants: list[dict[str, Any]] = []
        self.imports: list[dict[str, Any]] = []
        self.exports: list[str] = []
        self._module_docstring: str = ""
        self._in_class: bool = False
        self._current_class: ClassInfo | None = None

    def _get_docstring(self, node: ast.AST) -> str:
        """Extract docstring from a node."""
        return ast.get_docstring(node) or ""

    def _get_decorator_names(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
        """Extract decorator names from a node."""
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(f"{self._get_full_name(dec)}")
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(self._get_full_name(dec.func))
        return decorators

    def _get_full_name(self, node: ast.AST) -> str:
        """Get full dotted name from attribute node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_full_name(node.value)}.{node.attr}"
        return ""

    def _get_annotation_string(self, node: ast.AST | None) -> str | None:
        """Convert annotation AST to string representation."""
        if node is None:
            return None
        return ast.unparse(node)

    def _extract_function_params(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict[str, Any]]:
        """Extract function parameters."""
        params = []
        args = node.args

        # Handle positional args
        defaults_offset = len(args.args) - len(args.defaults)
        for i, arg in enumerate(args.args):
            if arg.arg == "self" or arg.arg == "cls":
                continue
            param: dict[str, Any] = {"name": arg.arg}
            if arg.annotation:
                param["type"] = self._get_annotation_string(arg.annotation)
            if i >= defaults_offset:
                default_idx = i - defaults_offset
                param["default"] = ast.unparse(args.defaults[default_idx])
                param["optional"] = True
            params.append(param)

        # Handle keyword-only args
        kw_defaults_offset = 0
        for i, arg in enumerate(args.kwonlyargs):
            param = {"name": arg.arg}
            if arg.annotation:
                param["type"] = self._get_annotation_string(arg.annotation)
            if args.kw_defaults[i] is not None:
                param["default"] = ast.unparse(args.kw_defaults[i])
                param["optional"] = True
            params.append(param)

        return params

    def visit_Module(self, node: ast.Module) -> None:
        """Visit module node."""
        self._module_docstring = self._get_docstring(node)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statement."""
        for alias in node.names:
            import_info: dict[str, Any] = {"module": alias.name}
            if alias.asname:
                import_info["alias"] = alias.asname
            self.imports.append(import_info)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from...import statement."""
        if node.module:
            import_info: dict[str, Any] = {
                "module": node.module,
                "names": [alias.name for alias in node.names],
                "is_relative": node.level > 0,
            }
            self.imports.append(import_info)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        decorators = self._get_decorator_names(node)
        bases = [self._get_full_name(base) for base in node.bases if self._get_full_name(base)]

        # Determine kind based on decorators/bases
        kind = "class"
        if "dataclass" in decorators or "dataclasses.dataclass" in decorators:
            kind = "dataclass"
        elif any(b in ("BaseModel", "pydantic.BaseModel") for b in bases):
            kind = "pydantic_model"
        elif any(b in ("TypedDict", "typing.TypedDict") for b in bases):
            kind = "typed_dict"
        elif any(b in ("Protocol", "typing.Protocol") for b in bases):
            kind = "protocol"
        elif any(b in ("Enum", "str, Enum", "IntEnum") for b in bases):
            kind = "enum"

        # If it's a type-like class, add to types
        if kind in ("typed_dict", "protocol", "enum"):
            type_info = TypeInfo(
                name=node.name,
                kind=kind,
                line=node.lineno,
                description=self._get_docstring(node),
                members=self._extract_type_members(node, kind),
            )
            self.types.append(type_info)
            return

        class_info = ClassInfo(
            name=node.name,
            line=node.lineno,
            description=self._get_docstring(node),
            bases=bases,
            decorators=decorators,
        )

        # Visit class body
        self._in_class = True
        self._current_class = class_info

        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self._extract_method(child)
                class_info.methods.append(method_info)
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                prop_info: dict[str, Any] = {
                    "name": child.target.id,
                    "line": child.lineno,
                }
                if child.annotation:
                    prop_info["type"] = self._get_annotation_string(child.annotation)
                class_info.properties.append(prop_info)

        self._in_class = False
        self._current_class = None
        self.classes.append(class_info)

    def _extract_method(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
        """Extract method information."""
        decorators = self._get_decorator_names(node)
        visibility = "public"
        if node.name.startswith("__") and not node.name.endswith("__"):
            visibility = "private"
        elif node.name.startswith("_"):
            visibility = "protected"

        method_info: dict[str, Any] = {
            "name": node.name,
            "line": node.lineno,
            "visibility": visibility,
            "async": isinstance(node, ast.AsyncFunctionDef),
        }

        if "staticmethod" in decorators:
            method_info["static"] = True
        if "classmethod" in decorators:
            method_info["class_method"] = True
        if decorators:
            method_info["decorators"] = decorators

        params = self._extract_function_params(node)
        if params:
            method_info["parameters"] = params

        if node.returns:
            method_info["return_type"] = self._get_annotation_string(node.returns)

        docstring = self._get_docstring(node)
        if docstring:
            # Extract first line of docstring
            method_info["description"] = docstring.split("\n")[0].strip()

        return method_info

    def _extract_type_members(self, node: ast.ClassDef, kind: str) -> list[dict[str, Any]]:
        """Extract members from enum or TypedDict."""
        members = []
        for child in node.body:
            if kind == "enum" and isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        member: dict[str, Any] = {"name": target.id}
                        if isinstance(child.value, ast.Constant):
                            member["value"] = str(child.value.value)
                        members.append(member)
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                member = {"name": child.target.id}
                if child.annotation:
                    member["type"] = self._get_annotation_string(child.annotation)
                members.append(member)
        return members

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        if self._in_class:
            return  # Methods are handled in visit_ClassDef
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        if self._in_class:
            return  # Methods are handled in visit_ClassDef
        self._visit_function(node, is_async=True)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        """Process function node."""
        func_info = FunctionInfo(
            name=node.name,
            line=node.lineno,
            description=self._get_docstring(node).split("\n")[0].strip() if self._get_docstring(node) else "",
            is_async=is_async,
            decorators=self._get_decorator_names(node),
            parameters=self._extract_function_params(node),
            return_type=self._get_annotation_string(node.returns),
        )
        self.functions.append(func_info)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignment (potential constant)."""
        if self._in_class:
            return
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                const_info: dict[str, Any] = {
                    "name": target.id,
                    "line": node.lineno,
                }
                if isinstance(node.value, ast.Constant):
                    const_info["value"] = str(node.value.value)
                    const_info["type"] = type(node.value.value).__name__
                self.constants.append(const_info)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Visit annotated assignment (potential type alias)."""
        if self._in_class:
            return
        if isinstance(node.target, ast.Name):
            # Check if it's a type alias (TypeAlias annotation or common pattern)
            if node.annotation:
                ann_str = self._get_annotation_string(node.annotation)
                if "TypeAlias" in (ann_str or "") or (
                    node.value and isinstance(node.value, ast.Subscript)
                ):
                    type_info = TypeInfo(
                        name=node.target.id,
                        kind="type_alias",
                        line=node.lineno,
                    )
                    self.types.append(type_info)


def extract_python_module(file_path: Path, base_path: Path) -> ModuleInfo:
    """Extract module information from a Python file."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning(f"Could not decode {file_path}")
        return ModuleInfo(
            name=file_path.name,
            path=str(file_path.relative_to(base_path)),
        )

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        logger.warning(f"Syntax error in {file_path}: {e}")
        return ModuleInfo(
            name=file_path.name,
            path=str(file_path.relative_to(base_path)),
        )

    extractor = PythonASTExtractor(source)
    extractor.visit(tree)

    # Extract __all__ for exports
    exports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                exports.append(elt.value)

    return ModuleInfo(
        name=file_path.name,
        path=str(file_path.relative_to(base_path)),
        description=extractor._module_docstring.split("\n")[0] if extractor._module_docstring else "",
        classes=[
            {
                "name": c.name,
                "line": c.line,
                "description": c.description,
                "bases": c.bases if c.bases else None,
                "decorators": c.decorators if c.decorators else None,
                "methods": c.methods if c.methods else None,
                "properties": c.properties if c.properties else None,
            }
            for c in extractor.classes
        ],
        functions=[
            {
                "name": f.name,
                "line": f.line,
                "description": f.description,
                "async": f.is_async,
                "return_type": f.return_type,
                "parameters": f.parameters if f.parameters else None,
            }
            for f in extractor.functions
        ],
        types=[
            {
                "name": t.name,
                "kind": t.kind,
                "line": t.line,
                "description": t.description,
                "members": t.members if t.members else None,
            }
            for t in extractor.types
        ],
        constants=extractor.constants,
        imports=extractor.imports,
        exports=exports if exports else None,
    )


def gather_python_package(package_path: Path, base_path: Path) -> dict[str, Any]:
    """Gather information from a Python package."""
    domains: dict[str, dict[str, Any]] = {}
    src_path = package_path / "src"

    if not src_path.exists():
        src_path = package_path

    # Find all Python files
    for py_file in src_path.rglob("*.py"):
        if "node_modules" in str(py_file) or "__pycache__" in str(py_file):
            continue

        rel_path = py_file.relative_to(src_path)
        parts = rel_path.parts

        # Skip if it's just the package root
        if len(parts) < 2:
            continue

        # Determine domain (first directory after package name)
        package_name = parts[0]  # e.g., "daw_agents"
        if len(parts) < 3:
            domain_name = "root"
        else:
            domain_name = parts[1]  # e.g., "agents", "models", etc.

        if domain_name not in domains:
            domains[domain_name] = {
                "name": domain_name,
                "path": f"src/{package_name}/{domain_name}" if domain_name != "root" else f"src/{package_name}",
                "description": "",
                "modules": [],
            }

        # Extract module info
        module_info = extract_python_module(py_file, src_path)

        # Clean up None values
        cleaned_module = {k: v for k, v in module_info.__dict__.items() if v is not None and v != [] and v != {}}
        domains[domain_name]["modules"].append(cleaned_module)

    return domains


def clean_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Remove None, empty lists, and empty dicts recursively."""
    cleaned: dict[str, Any] = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            v = clean_dict(v)
            if v:
                cleaned[k] = v
        elif isinstance(v, list):
            cleaned_list = []
            for item in v:
                if isinstance(item, dict):
                    cleaned_item = clean_dict(item)
                    if cleaned_item:
                        cleaned_list.append(cleaned_item)
                elif item is not None:
                    cleaned_list.append(item)
            if cleaned_list:
                cleaned[k] = cleaned_list
        else:
            cleaned[k] = v
    return cleaned


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Gather codebase map from source files")
    parser.add_argument("--incremental", action="store_true", help="Only update changed files")
    parser.add_argument("--package", choices=["daw-agents", "daw-frontend"], help="Only process specific package")
    args = parser.parse_args()

    logger.info("Starting codebase map gathering...")

    # Load existing map if incremental
    existing_map: dict[str, Any] = {}
    if args.incremental and CODEBASE_MAP_PATH.exists():
        existing_map = json.loads(CODEBASE_MAP_PATH.read_text())

    # Initialize new map
    codebase_map: dict[str, Any] = {
        "$schema": "./codebase_map.schema.json",
        "meta": {
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_name": "RADit - Reliable Agentic Determinism Intelligence Transformation",
            "description": "AI agent workbench enforcing deterministic SDLC through TDD, multi-agent orchestration, and MCP integration",
        },
        "packages": {},
    }

    # Process daw-agents package
    if not args.package or args.package == "daw-agents":
        daw_agents_path = PROJECT_ROOT / "packages" / "daw-agents"
        if daw_agents_path.exists():
            logger.info("Processing daw-agents package...")
            domains = gather_python_package(daw_agents_path, daw_agents_path)
            codebase_map["packages"]["daw-agents"] = {
                "name": "daw-agents",
                "language": "python",
                "path": "packages/daw-agents",
                "description": "Python backend with FastAPI, LangGraph agents, and MCP integration",
                "domains": clean_dict(domains),
            }

    # Process daw-frontend package (TypeScript - simplified for now)
    if not args.package or args.package == "daw-frontend":
        daw_frontend_path = PROJECT_ROOT / "packages" / "daw-frontend"
        if daw_frontend_path.exists():
            logger.info("Processing daw-frontend package...")
            # TypeScript extraction would require ts-morph or similar
            # For now, preserve existing structure
            if "daw-frontend" in existing_map.get("packages", {}):
                codebase_map["packages"]["daw-frontend"] = existing_map["packages"]["daw-frontend"]
            else:
                codebase_map["packages"]["daw-frontend"] = {
                    "name": "daw-frontend",
                    "language": "typescript",
                    "path": "packages/daw-frontend",
                    "description": "Next.js frontend with React, TypeScript, and Tailwind",
                    "domains": {},
                }

    # Preserve capabilities and integration points from existing map
    if "capabilities" in existing_map:
        codebase_map["capabilities"] = existing_map["capabilities"]
    if "integration_points" in existing_map:
        codebase_map["integration_points"] = existing_map["integration_points"]

    # Write output
    CODEBASE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CODEBASE_MAP_PATH, "w") as f:
        json.dump(codebase_map, f, indent=2)

    logger.info(f"Codebase map written to {CODEBASE_MAP_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
