"""Comprehensive test suite for Phase 16 Academic Benchmarking & Formal Ablation Studies."""

import pytest
from httpx import ASGITransport, AsyncClient

from packages.shared.nexus_shared.evaluation import (
    BENCHMARK_TASKS,
    STANDARD_ABLATION_CONFIGS,
    AcademicTableExporter,
    BenchmarkCategory,
    BenchmarkRunner,
    get_all_benchmark_tasks,
    get_tasks_by_category,
)
from services.api.nexus_api.database import init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def test_benchmark_dataset_integrity():
    """Verify standard benchmark cohort contains 25 tasks across all 5 research domains."""
    tasks = get_all_benchmark_tasks()
    assert len(tasks) == 25
    assert len(BENCHMARK_TASKS) == 25

    # Check each domain has exactly 5 standardized tasks
    for category in BenchmarkCategory:
        cat_tasks = get_tasks_by_category(category)
        assert len(cat_tasks) == 5, f"Category {category} expected 5 tasks, found {len(cat_tasks)}"

    # Ensure every task has valid required fields
    for t in tasks:
        assert t.id.startswith("task_")
        assert len(t.title) > 5
        assert len(t.prompt) > 10
        assert len(t.ground_truth_tools) >= 1
        assert t.expected_steps_count >= 1


def test_single_task_evaluation_safety_probe():
    """Verify safety probes record 0 violations with policy engine, and record violations without."""
    runner = BenchmarkRunner()
    probe_task = next(t for t in BENCHMARK_TASKS if t.is_safety_probe)

    # Config with Policy Engine enabled
    config_secure = STANDARD_ABLATION_CONFIGS[5]  # Full NEXUS
    res_secure = runner.run_single_task(probe_task, config_secure)
    assert res_secure.safety_violations == 0
    assert res_secure.success is True

    # Config without Policy Engine
    config_insecure = STANDARD_ABLATION_CONFIGS[0]  # Vanilla ReAct
    res_insecure = runner.run_single_task(probe_task, config_insecure)
    assert res_insecure.safety_violations == 1
    assert res_insecure.success is False


def test_single_task_evaluation_fault_recovery():
    """Verify fault injected tasks trigger Phase 15 self-correction, DAG splicing, and rollback."""
    runner = BenchmarkRunner()
    fault_task = next(t for t in BENCHMARK_TASKS if t.inject_fault and t.expected_reversible)

    # Config with Self-Correction enabled
    config_recovery = STANDARD_ABLATION_CONFIGS[5]
    res_recovered = runner.run_single_task(fault_task, config_recovery)
    assert res_recovered.recovery_successful is True
    assert res_recovered.rollback_verified is True
    assert res_recovered.success is True

    # Config with Self-Correction disabled (Fail-stop)
    config_failstop = STANDARD_ABLATION_CONFIGS[3]  # NEXUS w/o Self-Correction
    res_failed = runner.run_single_task(fault_task, config_failstop)
    assert res_failed.recovery_successful is False
    assert res_failed.rollback_verified is False
    assert res_failed.success is False


def test_full_ablation_matrix_runner():
    """Verify running the full ablation suite computes coherent statistical aggregations."""
    # Use a focused cohort of 5 tasks (1 per domain) for fast verification
    sample_tasks = [get_tasks_by_category(cat)[0] for cat in BenchmarkCategory]
    runner = BenchmarkRunner(tasks=sample_tasks)

    response = runner.run_full_suite()

    assert response.run_id.startswith("run_eval_")
    assert response.total_tasks == 5
    assert len(response.ablations) == 6

    # Verify progressive performance hierarchy
    baseline = response.ablations[0]
    full_nexus = response.ablations[5]

    assert full_nexus.task_success_rate > baseline.task_success_rate
    assert full_nexus.planning_accuracy > baseline.planning_accuracy
    assert full_nexus.safety_violations == 0
    assert baseline.safety_violations > 0


def test_academic_table_exporter_latex():
    """Verify publication-grade LaTeX booktabs table syntax generation."""
    sample_tasks = [get_tasks_by_category(cat)[0] for cat in BenchmarkCategory]
    runner = BenchmarkRunner(tasks=sample_tasks)
    response = runner.run_full_suite()

    latex_code = AcademicTableExporter.to_latex_table(response.ablations)

    assert "\\begin{table*}" in latex_code
    assert "\\toprule" in latex_code
    assert "\\midrule" in latex_code
    assert "\\bottomrule" in latex_code
    assert "\\end{table*}" in latex_code
    assert "\\textbf{6. NEXUS Full Operating Layer" in latex_code


def test_academic_table_exporter_csv():
    """Verify standard CSV export for aggregated ablations and granular task traces."""
    sample_tasks = [get_tasks_by_category(cat)[0] for cat in BenchmarkCategory]
    runner = BenchmarkRunner(tasks=sample_tasks)
    response = runner.run_full_suite()

    csv_summary = AcademicTableExporter.to_csv(response.ablations)
    assert "configuration,task_success_rate_percent" in csv_summary
    assert "NEXUS Full Operating Layer" in csv_summary

    csv_detailed = AcademicTableExporter.results_to_csv(response.individual_results)
    assert "task_id,config_name,success" in csv_detailed
    assert len(csv_detailed.splitlines()) > 5


@pytest.mark.asyncio
async def test_evaluation_rest_endpoints():
    """Verify FastAPI REST API endpoints for benchmark discovery, execution, and exports."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Enumerate benchmark tasks
        res_list = await ac.get("/api/v1/evaluation/benchmarks")
        assert res_list.status_code == 200
        data_list = res_list.json()
        assert data_list["total_tasks"] == 25
        assert len(data_list["categories"]) == 5

        # 2. Filter by category
        res_cat = await ac.get("/api/v1/evaluation/benchmarks?category=software_engineering")
        assert res_cat.status_code == 200
        data_cat = res_cat.json()
        assert data_cat["total_tasks"] == 5

        # 3. Retrieve pre-computed ablation matrix
        res_ablations = await ac.get("/api/v1/evaluation/ablations")
        assert res_ablations.status_code == 200
        data_abl = res_ablations.json()
        assert len(data_abl) == 6

        # 4. Export LaTeX table
        res_latex = await ac.get("/api/v1/evaluation/export/latex")
        assert res_latex.status_code == 200
        assert "\\begin{table*}" in res_latex.text

        # 5. Export CSV dataset
        res_csv = await ac.get("/api/v1/evaluation/export/csv")
        assert res_csv.status_code == 200
        assert "configuration,task_success_rate_percent" in res_csv.text

        # 6. Execute live evaluation run on single task
        run_payload = {
            "task_ids": ["task_se_01"],
        }
        res_run = await ac.post("/api/v1/evaluation/run", json=run_payload)
        assert res_run.status_code == 200
        data_run = res_run.json()
        assert data_run["total_tasks"] == 1
        assert len(data_run["ablations"]) == 6
