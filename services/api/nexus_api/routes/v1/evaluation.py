"""REST API endpoints for Phase 16 Academic Benchmarking & Formal Ablation Studies."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from packages.shared.nexus_shared.evaluation import (
    BENCHMARK_TASKS,
    STANDARD_ABLATION_CONFIGS,
    AblationConfig,
    AblationSummary,
    AcademicTableExporter,
    BenchmarkCategory,
    BenchmarkRunner,
    BenchmarkRunResponse,
    BenchmarkTask,
    get_all_benchmark_tasks,
    get_tasks_by_category,
)
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import UserModel
from services.api.nexus_api.auth.dependencies import get_optional_current_user

logger = get_logger("nexus.routes.evaluation")

evaluation_router = APIRouter(prefix="/evaluation", tags=["Academic Benchmarks & Evaluation"])


class RunEvaluationRequest(BaseModel):
    """Configuration for executing an evaluation experiment."""

    category: BenchmarkCategory | None = Field(
        default=None, description="Optional domain filter (e.g. software_engineering)"
    )
    task_ids: list[str] | None = Field(
        default=None, description="Optional list of specific task IDs to evaluate"
    )
    ablation_configs: list[AblationConfig] | None = Field(
        default=None, description="Custom ablation configs; defaults to STANDARD_ABLATION_CONFIGS"
    )


class BenchmarksListResponse(BaseModel):
    """Listing of available benchmark tasks and domain metadata."""

    total_tasks: int
    categories: dict[str, int]
    tasks: list[BenchmarkTask]


# Cache latest formal ablation run in-memory for instant dashboard retrieval
_CACHED_BENCHMARK_RUN: BenchmarkRunResponse | None = None


def _get_or_run_cached_benchmark() -> BenchmarkRunResponse:
    """Retrieve cached benchmark results or compute initial reference evaluation run."""
    global _CACHED_BENCHMARK_RUN
    if _CACHED_BENCHMARK_RUN is None:
        runner = BenchmarkRunner()
        _CACHED_BENCHMARK_RUN = runner.run_full_suite()
    return _CACHED_BENCHMARK_RUN


@evaluation_router.get("/benchmarks", response_model=BenchmarksListResponse)
async def list_benchmark_tasks(
    category: BenchmarkCategory | None = Query(
        default=None, description="Filter by evaluation category"
    ),
    _user: UserModel | None = Depends(get_optional_current_user),
) -> BenchmarksListResponse:
    """Enumerate the standardized cohort of academic benchmark evaluation tasks."""
    if category:
        tasks = get_tasks_by_category(category)
    else:
        tasks = get_all_benchmark_tasks()

    category_counts: dict[str, int] = {}
    for t in BENCHMARK_TASKS:
        cat_key = t.category.value
        category_counts[cat_key] = category_counts.get(cat_key, 0) + 1

    return BenchmarksListResponse(
        total_tasks=len(tasks),
        categories=category_counts,
        tasks=tasks,
    )


@evaluation_router.post("/run", response_model=BenchmarkRunResponse)
async def run_benchmark_evaluation(
    req: RunEvaluationRequest,
    _user: UserModel | None = Depends(get_optional_current_user),
) -> BenchmarkRunResponse:
    """Execute live evaluation suite across selected benchmark tasks and ablation configurations."""
    global _CACHED_BENCHMARK_RUN

    # Resolve task selection
    if req.task_ids:
        tasks = [t for t in BENCHMARK_TASKS if t.id in req.task_ids]
        if not tasks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="None of the specified task_ids match known benchmark tasks",
            )
    elif req.category:
        tasks = get_tasks_by_category(req.category)
    else:
        tasks = get_all_benchmark_tasks()

    configs = req.ablation_configs or STANDARD_ABLATION_CONFIGS

    logger.info(
        "executing_benchmark_evaluation",
        task_count=len(tasks),
        config_count=len(configs),
    )

    runner = BenchmarkRunner(tasks=tasks)
    result = runner.run_full_suite(configs=configs)

    # Update cache if evaluating standard suite
    if not req.task_ids and not req.category and not req.ablation_configs:
        _CACHED_BENCHMARK_RUN = result

    return result


@evaluation_router.get("/ablations", response_model=list[AblationSummary])
async def get_ablation_matrix(
    _user: UserModel | None = Depends(get_optional_current_user),
) -> list[AblationSummary]:
    """Retrieve statistical summary of the formal architectural ablation matrix."""
    bench_run = _get_or_run_cached_benchmark()
    return bench_run.ablations


@evaluation_router.get("/export/latex")
async def export_latex_table(
    caption: str = Query(
        default="Empirical Evaluation across Architectural Ablations on Standardized NEXUS Tasks (N=25)",
        description="Custom LaTeX table caption",
    ),
    label: str = Query(
        default="tab:nexus_ablation_matrix", description="LaTeX table label"
    ),
    _user: UserModel | None = Depends(get_optional_current_user),
) -> Response:
    """Generate publication-ready LaTeX table with booktabs formatting for paper submission."""
    bench_run = _get_or_run_cached_benchmark()
    latex_code = AcademicTableExporter.to_latex_table(
        bench_run.ablations, caption=caption, label=label
    )
    return Response(
        content=latex_code,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "inline; filename=nexus_ablation_matrix.tex"},
    )


@evaluation_router.get("/export/csv")
async def export_csv_dataset(
    detailed: bool = Query(
        default=False, description="If true, returns per-task granular telemetry results"
    ),
    _user: UserModel | None = Depends(get_optional_current_user),
) -> Response:
    """Export benchmark evaluation results in standard CSV format for plotting."""
    bench_run = _get_or_run_cached_benchmark()
    if detailed:
        csv_data = AcademicTableExporter.results_to_csv(bench_run.individual_results)
        filename = "nexus_benchmark_individual_results.csv"
    else:
        csv_data = AcademicTableExporter.to_csv(bench_run.ablations)
        filename = "nexus_ablation_matrix.csv"

    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
