"""Benchmark suite to evaluate LLM performance backing the agentic system."""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from agent import run_agent, OLLAMA_MODEL, BACKEND, BEDROCK_MODEL_ID
from database import init_db
from cache import clear_all_cache, clear_expired_cache


@dataclass
class BenchmarkResult:
    """Result of a single benchmark test."""
    name: str
    category: str
    passed: bool
    score: float  # 0.0 to 1.0
    answer: str
    elapsed_seconds: float
    failure_reason: Optional[str] = None


@dataclass
class BenchmarkCase:
    """A single benchmark test case."""
    name: str
    category: str
    question: str
    validators: list[Callable[[str], tuple[bool, str]]]
    weight: float = 1.0
    conversation_history: Optional[list[dict]] = None

    def run(self) -> BenchmarkResult:
        """Execute this benchmark case and return the result."""
        start = time.perf_counter()
        try:
            answer = run_agent(
                self.question,
                conversation_history=self.conversation_history,
            )
        except Exception as e:
            elapsed = time.perf_counter() - start
            return BenchmarkResult(
                name=self.name,
                category=self.category,
                passed=False,
                score=0.0,
                answer=f"ERROR: {e}",
                elapsed_seconds=elapsed,
                failure_reason=f"Agent raised exception: {e}",
            )

        elapsed = time.perf_counter() - start

        # Run all validators
        failures = []
        for validator in self.validators:
            passed, reason = validator(answer)
            if not passed:
                failures.append(reason)

        if failures:
            return BenchmarkResult(
                name=self.name,
                category=self.category,
                passed=False,
                score=max(0.0, 1.0 - len(failures) / len(self.validators)),
                answer=answer,
                elapsed_seconds=elapsed,
                failure_reason="; ".join(failures),
            )

        return BenchmarkResult(
            name=self.name,
            category=self.category,
            passed=True,
            score=1.0,
            answer=answer,
            elapsed_seconds=elapsed,
        )


# =============================================================================
# VALIDATORS
# =============================================================================

def contains_number(target: float, tolerance: float = 0.5) -> Callable[[str], tuple[bool, str]]:
    """Validator: answer must contain a specific number (within absolute tolerance).

    Args:
        target: The expected number
        tolerance: Absolute allowed difference (default 0.5, so 15 accepts 14.5-15.5)
    """
    def validate(answer: str) -> tuple[bool, str]:
        # Extract all numbers from the answer (handles commas in large numbers)
        numbers = re.findall(r'[\d,]+\.?\d*', answer.replace(',', ''))
        found_numbers = []
        for num_str in numbers:
            try:
                num = float(num_str.replace(',', ''))
                found_numbers.append(num)
                if abs(num - target) <= tolerance:
                    return True, ""
            except ValueError:
                continue
        # Show what numbers we found for debugging
        return False, f"Expected ~{target} (±{tolerance}), found: {found_numbers[:5]}"
    return validate


def contains_any_of(*keywords: str) -> Callable[[str], tuple[bool, str]]:
    """Validator: answer must contain at least one of the keywords (case-insensitive)."""
    def validate(answer: str) -> tuple[bool, str]:
        answer_lower = answer.lower()
        for kw in keywords:
            if kw.lower() in answer_lower:
                return True, ""
        return False, f"Expected one of {keywords} in answer"
    return validate


def contains_all_of(*keywords: str) -> Callable[[str], tuple[bool, str]]:
    """Validator: answer must contain all keywords (case-insensitive)."""
    def validate(answer: str) -> tuple[bool, str]:
        answer_lower = answer.lower()
        missing = [kw for kw in keywords if kw.lower() not in answer_lower]
        if missing:
            return False, f"Missing keywords: {missing}"
        return True, ""
    return validate


def does_not_contain(*keywords: str) -> Callable[[str], tuple[bool, str]]:
    """Validator: answer must NOT contain any of these keywords."""
    def validate(answer: str) -> tuple[bool, str]:
        answer_lower = answer.lower()
        found = [kw for kw in keywords if kw.lower() in answer_lower]
        if found:
            return False, f"Answer should not contain: {found}"
        return True, ""
    return validate


def is_reasonable_length(min_words: int = 5, max_words: int = 500) -> Callable[[str], tuple[bool, str]]:
    """Validator: answer should be a reasonable length."""
    def validate(answer: str) -> tuple[bool, str]:
        word_count = len(answer.split())
        if word_count < min_words:
            return False, f"Answer too short ({word_count} words, min {min_words})"
        if word_count > max_words:
            return False, f"Answer too long ({word_count} words, max {max_words})"
        return True, ""
    return validate


def not_an_error() -> Callable[[str], tuple[bool, str]]:
    """Validator: answer should not be an error message."""
    def validate(answer: str) -> tuple[bool, str]:
        error_indicators = ["error:", "failed", "exception", "invalid", "could not"]
        answer_lower = answer.lower()
        for indicator in error_indicators:
            if answer_lower.startswith(indicator):
                return False, f"Answer appears to be an error: {answer[:100]}"
        return True, ""
    return validate


# =============================================================================
# BENCHMARK CASES
# =============================================================================

BENCHMARK_CASES = [
    # Category 1: Simple Queries
    BenchmarkCase(
        name="count_games",
        category="simple_query",
        question="How many different board games do we have in our inventory?",
        validators=[
            contains_number(15),  # 15 games in database
            not_an_error(),
        ],
    ),
    BenchmarkCase(
        name="most_expensive_game",
        category="simple_query",
        question="What is our most expensive board game?",
        validators=[
            contains_any_of("Gloomhaven"),
            contains_number(139.99, tolerance=1.0),  # $138.99-$140.99
            not_an_error(),
        ],
    ),

    # Category 2: Multi-step Reasoning
    BenchmarkCase(
        name="top_seller_details",
        category="multi_step",
        question="What is our best-selling game, and what category is it in?",
        validators=[
            contains_any_of("Exploding Kittens"),
            contains_any_of("Party"),
            not_an_error(),
        ],
    ),
    BenchmarkCase(
        name="category_with_most_stock",
        category="multi_step",
        question="Which category of games has the most total units in stock?",
        validators=[
            # Party has 35 (Codenames 15 + Exploding Kittens 20)
            contains_any_of("Party"),
            not_an_error(),
        ],
    ),

    # Category 3: Calculation Required
    BenchmarkCase(
        name="average_game_price",
        category="calculation",
        question="What is the average retail price of all our board games?",
        validators=[
            # Average of all 15 games: $50.99
            contains_number(50.99, tolerance=1.0),  # $49.99-$51.99
            not_an_error(),
        ],
    ),
    BenchmarkCase(
        name="total_inventory_value",
        category="calculation",
        question="What is the total retail value of all games currently in stock?",
        validators=[
            # Sum of (price * in_stock) for all games = $4,568.84
            contains_number(4568.84, tolerance=100),  # $4,468-$4,668
            not_an_error(),
        ],
    ),

    # Category 4: Comparison / Percentage
    BenchmarkCase(
        name="percentage_strategy_games",
        category="comparison",
        question="What percentage of our total game inventory (by unit count) is Strategy games?",
        validators=[
            # Strategy: 32 units out of 116 total = 27.6%
            contains_number(27.6, tolerance=2),
            contains_any_of("%", "percent"),
            not_an_error(),
        ],
    ),
    BenchmarkCase(
        name="online_vs_instore_sales",
        category="comparison",
        question="What percentage of our game sales revenue comes from online orders versus in-store?",
        validators=[
            # Should mention both online and in-store with percentages
            # Actual: ~51% online, ~49% in-store
            contains_any_of("online"),
            contains_any_of("in-store", "in_store", "in store", "store"),
            contains_any_of("%", "percent"),
            contains_number(51, tolerance=10),  # Online should be ~41-61%
            not_an_error(),
        ],
        weight=1.5,  # Harder question, worth more
    ),

    # Category 5: What-if Scenarios
    BenchmarkCase(
        name="whatif_price_increase",
        category="whatif",
        question="What would happen to our game revenue if we increased all game prices by 10%?",
        validators=[
            contains_any_of("10%", "10 percent", "increase"),
            contains_any_of("revenue", "sales", "$"),
            not_an_error(),
        ],
    ),
    BenchmarkCase(
        name="whatif_expense_reduction",
        category="whatif",
        question="How would our expenses change if we reduced labor costs by 15%?",
        validators=[
            contains_any_of("labor", "15%", "15 percent"),
            contains_any_of("save", "reduce", "decrease", "less", "$"),
            not_an_error(),
        ],
    ),

    # Category 6: Conversation Follow-up
    BenchmarkCase(
        name="followup_question",
        category="followup",
        question="How many of those do we have in stock?",
        conversation_history=[
            {"role": "user", "content": "What is our cheapest board game?"},
            {"role": "assistant", "content": "Our cheapest board games are Codenames and Exploding Kittens, both priced at $19.99."},
        ],
        validators=[
            # Should understand "those" refers to Codenames/Exploding Kittens
            # Codenames: 15, Exploding Kittens: 20
            contains_any_of("15", "20", "35"),
            not_an_error(),
        ],
        weight=1.5,
    ),

    # Category 7: Graceful Failure / Edge Cases
    BenchmarkCase(
        name="no_data_available",
        category="edge_case",
        question="How many customers visited the cafe last month?",
        validators=[
            # Should acknowledge we don't have customer visit data
            contains_any_of("don't have", "no data", "not available", "cannot", "don't track"),
            does_not_contain("150", "200", "300"),  # Should not hallucinate numbers
            not_an_error(),
        ],
    ),
    BenchmarkCase(
        name="ambiguous_question",
        category="edge_case",
        question="What's our profit?",
        validators=[
            # Should either ask for clarification or provide some reasonable profit calculation
            is_reasonable_length(min_words=10),
            not_an_error(),
        ],
    ),
]


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

@dataclass
class BenchmarkSummary:
    """Summary of all benchmark results."""
    model: str
    backend: str
    total_cases: int
    passed: int
    failed: int
    total_score: float
    max_score: float
    percentage: float
    total_time_seconds: float
    avg_time_per_case: float
    results_by_category: dict[str, dict]
    individual_results: list[BenchmarkResult]


def run_benchmark(
    cases: Optional[list[BenchmarkCase]] = None,
    verbose: bool = True,
    no_cache: bool = False,
) -> BenchmarkSummary:
    """
    Run the full benchmark suite and return a summary.

    Args:
        cases: List of cases to run (defaults to all BENCHMARK_CASES)
        verbose: Print progress as tests run
        no_cache: If True, clear all cache before running

    Returns:
        BenchmarkSummary with overall score and detailed results
    """
    if cases is None:
        cases = BENCHMARK_CASES

    # Clear cache if requested
    if no_cache:
        clear_all_cache()

    # Always clear expired cache entries
    clear_expired_cache()

    # Ensure DB is initialized
    init_db()

    # Get model info
    if BACKEND == "ollama":
        model = OLLAMA_MODEL
    else:
        model = BEDROCK_MODEL_ID

    if verbose:
        print(f"\n{'='*60}")
        print(f"BENCHMARK: {model} ({BACKEND})")
        print(f"{'='*60}\n")

    # Warmup query to avoid cold start penalty on first real test
    if verbose:
        print("[warmup] Loading model...", end=" ", flush=True)
    try:
        warmup_start = time.perf_counter()
        run_agent("How many tables do we have?")  # Simple query to wake up the model
        warmup_time = time.perf_counter() - warmup_start
        if verbose:
            print(f"ready ({warmup_time:.1f}s)\n")
    except Exception:
        if verbose:
            print("failed (continuing anyway)\n")

    results: list[BenchmarkResult] = []
    total_start = time.perf_counter()

    for i, case in enumerate(cases, 1):
        if verbose:
            print(f"[{i}/{len(cases)}] {case.category}/{case.name}...", end=" ", flush=True)

        result = case.run()
        results.append(result)

        if verbose:
            status = "PASS" if result.passed else "FAIL"
            print(f"{status} ({result.elapsed_seconds:.1f}s)")
            if not result.passed and result.failure_reason:
                print(f"       Reason: {result.failure_reason[:80]}")

    total_time = time.perf_counter() - total_start

    # Calculate scores
    total_score = sum(r.score * cases[i].weight for i, r in enumerate(results))
    max_score = sum(c.weight for c in cases)
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    # Group by category
    results_by_category: dict[str, dict] = {}
    for case, result in zip(cases, results):
        cat = case.category
        if cat not in results_by_category:
            results_by_category[cat] = {"passed": 0, "failed": 0, "score": 0.0, "max_score": 0.0}
        results_by_category[cat]["max_score"] += case.weight
        results_by_category[cat]["score"] += result.score * case.weight
        if result.passed:
            results_by_category[cat]["passed"] += 1
        else:
            results_by_category[cat]["failed"] += 1

    summary = BenchmarkSummary(
        model=model,
        backend=BACKEND,
        total_cases=len(cases),
        passed=passed,
        failed=failed,
        total_score=total_score,
        max_score=max_score,
        percentage=(total_score / max_score * 100) if max_score > 0 else 0,
        total_time_seconds=total_time,
        avg_time_per_case=total_time / len(cases) if cases else 0,
        results_by_category=results_by_category,
        individual_results=results,
    )

    if verbose:
        print_summary(summary)

    return summary


def print_summary(summary: BenchmarkSummary) -> None:
    """Print a formatted summary of benchmark results."""
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"Model: {summary.model} ({summary.backend})")
    print(f"Total time: {summary.total_time_seconds:.1f}s (avg {summary.avg_time_per_case:.1f}s/case)")
    print()
    print(f"Overall: {summary.passed}/{summary.total_cases} passed")
    print(f"Score: {summary.total_score:.2f}/{summary.max_score:.2f} ({summary.percentage:.1f}%)")
    print()
    print("By Category:")
    for cat, stats in sorted(summary.results_by_category.items()):
        cat_pct = (stats["score"] / stats["max_score"] * 100) if stats["max_score"] > 0 else 0
        print(f"  {cat}: {stats['passed']}/{stats['passed']+stats['failed']} ({cat_pct:.0f}%)")
    print()
    print(f"{'='*60}")
    print(f"FINAL SCORE: {summary.percentage:.1f}%")
    print(f"{'='*60}\n")


def get_score(cases: Optional[list[BenchmarkCase]] = None) -> float:
    """
    Run benchmark and return just the percentage score.

    This is the single-number metric for model comparison.
    """
    summary = run_benchmark(cases=cases, verbose=False)
    return summary.percentage


if __name__ == "__main__":
    import sys

    # Check for --no-cache flag
    no_cache = "--no-cache" in sys.argv
    args = [arg for arg in sys.argv[1:] if arg != "--no-cache"]

    # Allow running a specific case by name
    if len(args) > 0:
        case_name = args[0]
        matching = [c for c in BENCHMARK_CASES if c.name == case_name]
        if matching:
            print(f"Running single case: {case_name}")
            summary = run_benchmark(cases=matching, no_cache=no_cache)
            # Show the answer for single case runs
            for r in summary.individual_results:
                print(f"\nAnswer: {r.answer}")
        else:
            print(f"Unknown case: {case_name}")
            print("Available cases:")
            for c in BENCHMARK_CASES:
                print(f"  - {c.name} ({c.category})")
            sys.exit(1)
    else:
        # Run full benchmark
        summary = run_benchmark(no_cache=no_cache)

        # Show ALL case details
        print("\nALL CASES DETAIL:")
        print("-" * 40)
        for r in summary.individual_results:
            status = "PASS" if r.passed else "FAIL"
            print(f"\n[{status}] {r.category}/{r.name}:")
            if r.failure_reason:
                print(f"  Reason: {r.failure_reason}")
            # Truncate long answers but show more context
            answer_display = r.answer[:300] + "..." if len(r.answer) > 300 else r.answer
            print(f"  Answer: {answer_display}")
