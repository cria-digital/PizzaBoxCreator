"""Run a small benchmark against the configured LLM provider.

Usage examples:
  AI_PROVIDER=ollama OLLAMA_MODEL=llama3.2:3b .venv/bin/python scripts/benchmark_llm_models.py
  AI_PROVIDER=gemini GEMINI_API_KEY=... .venv/bin/python scripts/benchmark_llm_models.py --output temp/gemini.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any

from app.ai.agent import DesignAgent
from app.config import settings


DEFAULT_CASES: list[dict[str, Any]] = [
    {
        "name": "pedido_completo_premium",
        "message": (
            "Cliente Pizzaria Bella, telefone 11999998888, caixa premium preta, "
            "instagram @pizzabella e selo delivery"
        ),
        "expected": {
            "telefone": "11999998888",
            "instagram": "@pizzabella",
            "tema_fundo": "premium",
            "adicionar_selo_entrega": True,
            "adicionar_forno_lenha": False,
        },
    },
    {
        "name": "tradicional_forno",
        "message": (
            "Quero caixa kraft tradicional com frase Bom Apetite, telefone (51) 98888-7777, "
            "com desenho de forno a lenha"
        ),
        "expected": {
            "telefone": "(51) 98888-7777",
            "tema_fundo": "tradicional",
            "adicionar_forno_lenha": True,
            "adicionar_selo_entrega": False,
        },
    },
    {
        "name": "instagram_sem_arroba",
        "message": "Adicionar instagram pizzaria_do_centro e deixar visual elegante escuro",
        "expected": {
            "instagram": "@pizzaria_do_centro",
            "tema_fundo": "premium",
            "adicionar_selo_entrega": False,
            "adicionar_forno_lenha": False,
        },
    },
    {
        "name": "fora_do_escopo",
        "message": "Quero mudar o formato da faca da caixa para um modelo totalmente novo",
        "expected_error": True,
    },
]


def _load_cases(path: Path | None) -> list[dict[str, Any]]:
    if not path:
        return DEFAULT_CASES
    cases: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for key, value in data.items():
        if hasattr(value, "value"):
            normalized[key] = value.value
        else:
            normalized[key] = value
    return normalized


def _score(result: dict[str, Any], expected: dict[str, Any]) -> tuple[int, int, bool]:
    total = len(expected)
    hits = sum(1 for key, value in expected.items() if result.get(key) == value)
    return hits, total, hits == total


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark LLM parsing quality for Pizza Box Agent.")
    parser.add_argument("--cases", type=Path, help="Optional JSONL file with benchmark cases.")
    parser.add_argument("--output", type=Path, default=Path("temp/llm_benchmark.csv"))
    parser.add_argument("--provider", help="Override AI_PROVIDER for this run.")
    parser.add_argument("--ollama-model", help="Override OLLAMA_MODEL for this run.")
    args = parser.parse_args()

    if args.provider:
        settings.ai_provider = args.provider
    if args.ollama_model:
        settings.ollama_model = args.ollama_model

    cases = _load_cases(args.cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    agent = DesignAgent()
    rows: list[dict[str, Any]] = []
    passed = 0
    total_fields = 0
    hit_fields = 0

    for case in cases:
        started = time.perf_counter()
        error = ""
        result: dict[str, Any] = {}
        ok = False
        hits = 0
        field_total = len(case.get("expected", {}))

        try:
            command = agent.parse_message(case["message"])
            result = _normalize(command.model_dump(exclude_none=True))
            if case.get("expected_error"):
                ok = False
                error = "expected_error_but_model_returned_command"
            else:
                hits, field_total, ok = _score(result, case.get("expected", {}))
        except Exception as exc:  # noqa: BLE001 - benchmark records provider/model failures
            error = str(exc)
            ok = bool(case.get("expected_error"))
            if ok:
                hits = 1
                field_total = 1

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        passed += int(ok)
        hit_fields += hits
        total_fields += field_total
        rows.append({
            "provider": settings.ai_provider,
            "model": settings.ollama_model if settings.ai_provider == "ollama" else "",
            "case": case["name"],
            "ok": ok,
            "field_hits": hits,
            "field_total": field_total,
            "latency_ms": elapsed_ms,
            "error": error,
            "result_json": json.dumps(result, ensure_ascii=False, sort_keys=True),
        })

    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    field_rate = (hit_fields / total_fields) if total_fields else 0
    print(f"Provider: {settings.ai_provider}")
    print(f"Cases OK: {passed}/{len(cases)}")
    print(f"Field accuracy: {field_rate:.1%}")
    print(f"CSV: {args.output}")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
