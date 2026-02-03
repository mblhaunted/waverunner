#!/usr/bin/env python3
"""
Waverunner Benchmark Suite

Compares Waverunner outputs against baseline expectations.
Not part of main test suite - run manually with: python3 benchmark.py

Tracks:
- Lines of code produced
- Files created
- Test coverage
- Documentation quality
- Feature completeness
- Error handling
- Time to completion
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict


@dataclass
class BenchmarkResult:
    """Results from analyzing a codebase."""

    # Basic metrics
    total_files: int
    total_lines: int
    source_lines: int
    test_lines: int
    doc_lines: int

    # File breakdown
    source_files: int
    test_files: int
    doc_files: int
    config_files: int

    # Quality metrics
    has_tests: bool
    has_docs: bool
    has_error_handling: bool
    has_validation: bool
    has_database: bool

    # Feature completeness (0-1 score)
    feature_completeness: float

    # Calculated scores
    test_coverage_ratio: float  # test_lines / source_lines
    documentation_ratio: float   # doc_files / total_files

    # Metadata
    implementation_name: str
    analyzed_at: float


class CodebaseAnalyzer:
    """Analyze a codebase for benchmark metrics."""

    def __init__(self, path: Path):
        self.path = path

    def count_lines(self, file_path: Path) -> int:
        """Count non-empty lines in a file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def analyze(self, name: str) -> BenchmarkResult:
        """Analyze codebase and return metrics."""

        if not self.path.exists():
            print(f"⚠️  Path does not exist: {self.path}")
            return None

        source_files = []
        test_files = []
        doc_files = []
        config_files = []

        # Scan directory
        for root, dirs, files in os.walk(self.path):
            # Skip common ignore directories
            dirs[:] = [d for d in dirs if d not in {
                'node_modules', 'venv', '.venv', '__pycache__',
                'dist', 'build', '.git', 'uploads'
            }]

            for file in files:
                file_path = Path(root) / file
                ext = file_path.suffix.lower()

                # Skip binary files
                if ext in {'.db', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.pyc'}:
                    continue

                # Categorize files
                if file.startswith('test_') or 'test' in file.lower():
                    test_files.append(file_path)
                elif ext in {'.md', '.txt', '.rst'} or 'README' in file or 'CHANGELOG' in file:
                    doc_files.append(file_path)
                elif file in {'package.json', 'requirements.txt', 'setup.py',
                              'pyproject.toml', 'vite.config.js', '.waverunner.yaml'}:
                    config_files.append(file_path)
                elif ext in {'.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css'}:
                    source_files.append(file_path)

        # Count lines
        source_lines = sum(self.count_lines(f) for f in source_files)
        test_lines = sum(self.count_lines(f) for f in test_files)
        doc_lines = sum(self.count_lines(f) for f in doc_files)

        total_files = len(source_files) + len(test_files) + len(doc_files) + len(config_files)
        total_lines = source_lines + test_lines + doc_lines

        # Quality checks
        has_tests = len(test_files) > 0
        has_docs = len(doc_files) > 0
        has_error_handling = self._check_error_handling(source_files)
        has_validation = self._check_validation(source_files)
        has_database = self._check_database(source_files)

        # Calculate ratios
        test_coverage_ratio = test_lines / source_lines if source_lines > 0 else 0.0
        documentation_ratio = len(doc_files) / total_files if total_files > 0 else 0.0

        # Feature completeness (based on expected features)
        feature_score = sum([
            has_tests * 0.3,
            has_docs * 0.2,
            has_error_handling * 0.2,
            has_validation * 0.15,
            has_database * 0.15
        ])

        return BenchmarkResult(
            total_files=total_files,
            total_lines=total_lines,
            source_lines=source_lines,
            test_lines=test_lines,
            doc_lines=doc_lines,
            source_files=len(source_files),
            test_files=len(test_files),
            doc_files=len(doc_files),
            config_files=len(config_files),
            has_tests=has_tests,
            has_docs=has_docs,
            has_error_handling=has_error_handling,
            has_validation=has_validation,
            has_database=has_database,
            feature_completeness=feature_score,
            test_coverage_ratio=test_coverage_ratio,
            documentation_ratio=documentation_ratio,
            implementation_name=name,
            analyzed_at=time.time()
        )

    def _check_error_handling(self, files: List[Path]) -> bool:
        """Check if codebase has error handling."""
        patterns = ['try:', 'except', 'catch', 'throw', 'raise', 'Error(']
        return self._check_patterns(files, patterns, min_occurrences=3)

    def _check_validation(self, files: List[Path]) -> bool:
        """Check if codebase has input validation."""
        patterns = ['validate', 'if not', 'assert', 'required', 'check']
        return self._check_patterns(files, patterns, min_occurrences=5)

    def _check_database(self, files: List[Path]) -> bool:
        """Check if codebase uses a database."""
        patterns = ['sqlite', 'database', 'db.', 'localStorage', 'INSERT', 'SELECT']
        return self._check_patterns(files, patterns, min_occurrences=2)

    def _check_patterns(self, files: List[Path], patterns: List[str], min_occurrences: int) -> bool:
        """Check if patterns appear in files."""
        count = 0
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    for pattern in patterns:
                        if pattern in content:
                            count += 1
                            if count >= min_occurrences:
                                return True
            except Exception:
                continue
        return False


def compare_results(results: List[BenchmarkResult]) -> Dict:
    """Compare multiple benchmark results."""

    if not results:
        return {}

    comparison = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'implementations': {},
        'winner': {}
    }

    # Store each result
    for result in results:
        comparison['implementations'][result.implementation_name] = asdict(result)

    # Determine winners in each category
    comparison['winner'] = {
        'most_code': max(results, key=lambda r: r.total_lines).implementation_name,
        'most_tests': max(results, key=lambda r: r.test_lines).implementation_name,
        'most_docs': max(results, key=lambda r: r.doc_lines).implementation_name,
        'best_test_coverage': max(results, key=lambda r: r.test_coverage_ratio).implementation_name,
        'best_documentation': max(results, key=lambda r: r.documentation_ratio).implementation_name,
        'most_features': max(results, key=lambda r: r.feature_completeness).implementation_name,
    }

    return comparison


def print_result(result: BenchmarkResult):
    """Pretty print a benchmark result."""

    print(f"\n{'='*60}")
    print(f"📊 {result.implementation_name}")
    print(f"{'='*60}")

    print(f"\n📁 Files:")
    print(f"   Total files:      {result.total_files}")
    print(f"   Source files:     {result.source_files}")
    print(f"   Test files:       {result.test_files}")
    print(f"   Doc files:        {result.doc_files}")
    print(f"   Config files:     {result.config_files}")

    print(f"\n📝 Lines of Code:")
    print(f"   Total lines:      {result.total_lines:,}")
    print(f"   Source lines:     {result.source_lines:,}")
    print(f"   Test lines:       {result.test_lines:,}")
    print(f"   Doc lines:        {result.doc_lines:,}")

    print(f"\n✅ Quality Indicators:")
    print(f"   Has tests:        {'✓' if result.has_tests else '✗'}")
    print(f"   Has docs:         {'✓' if result.has_docs else '✗'}")
    print(f"   Error handling:   {'✓' if result.has_error_handling else '✗'}")
    print(f"   Input validation: {'✓' if result.has_validation else '✗'}")
    print(f"   Database:         {'✓' if result.has_database else '✗'}")

    print(f"\n📈 Scores:")
    print(f"   Test coverage:    {result.test_coverage_ratio:.2f} ({result.test_lines}/{result.source_lines} ratio)")
    print(f"   Documentation:    {result.documentation_ratio:.2%}")
    print(f"   Features:         {result.feature_completeness:.0%}")


def print_comparison(comparison: Dict):
    """Pretty print comparison results."""

    print(f"\n{'='*60}")
    print(f"🏆 COMPARISON SUMMARY")
    print(f"{'='*60}")

    winners = comparison.get('winner', {})

    print(f"\n🥇 Category Winners:")
    for category, winner in winners.items():
        print(f"   {category.replace('_', ' ').title():.<40} {winner}")

    print(f"\n📊 Detailed Comparison:")

    impls = comparison.get('implementations', {})
    if len(impls) >= 2:
        names = list(impls.keys())
        r1, r2 = impls[names[0]], impls[names[1]]

        print(f"\n   {'Metric':<30} {names[0]:<20} {names[1]:<20}")
        print(f"   {'-'*30} {'-'*20} {'-'*20}")
        print(f"   {'Total Lines':<30} {r1['total_lines']:>19,} {r2['total_lines']:>19,}")
        print(f"   {'Source Lines':<30} {r1['source_lines']:>19,} {r2['source_lines']:>19,}")
        print(f"   {'Test Lines':<30} {r1['test_lines']:>19,} {r2['test_lines']:>19,}")
        print(f"   {'Test Coverage Ratio':<30} {r1['test_coverage_ratio']:>19.2f} {r2['test_coverage_ratio']:>19.2f}")
        print(f"   {'Documentation Files':<30} {r1['doc_files']:>19} {r2['doc_files']:>19}")
        print(f"   {'Feature Completeness':<30} {r1['feature_completeness']:>18.0%} {r2['feature_completeness']:>18.0%}")


def save_results(comparison: Dict, output_file: str = 'benchmark_results.json'):
    """Save results to JSON file."""
    with open(output_file, 'w') as f:
        json.dump(comparison, f, indent=2)
    print(f"\n💾 Results saved to: {output_file}")


def main():
    """Run benchmark suite."""

    print("🏁 Waverunner Benchmark Suite")
    print("="*60)

    # Define implementations to compare
    benchmarks = [
        ("Waverunner (rescue)", Path.home() / "Documents" / "dev" / "rescue"),
        ("Regular Claude (foo)", Path.home() / "foo"),
    ]

    results = []

    for name, path in benchmarks:
        print(f"\n🔍 Analyzing: {name}")
        print(f"   Path: {path}")

        analyzer = CodebaseAnalyzer(path)
        result = analyzer.analyze(name)

        if result:
            results.append(result)
            print_result(result)
        else:
            print(f"   ⚠️  Skipped (path not found)")

    # Compare results
    if len(results) >= 2:
        comparison = compare_results(results)
        print_comparison(comparison)
        save_results(comparison)
    elif len(results) == 1:
        print("\n⚠️  Only one implementation found - need at least 2 for comparison")
    else:
        print("\n❌ No implementations found to benchmark")
        return 1

    print("\n✅ Benchmark complete!\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
