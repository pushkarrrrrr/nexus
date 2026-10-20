"""Academic table and dataset exporter generating publication-ready LaTeX and CSV outputs."""

import csv
import io

from packages.shared.nexus_shared.evaluation.schemas import AblationSummary, TaskRunResult


class AcademicTableExporter:
    """Formats benchmark summaries into LaTeX booktabs tables and CSV datasets."""

    @staticmethod
    def to_latex_table(
        summaries: list[AblationSummary],
        caption: str = "Empirical Evaluation across Architectural Ablations on Standardized NEXUS Tasks (N=25)",
        label: str = "tab:nexus_ablation_matrix",
    ) -> str:
        """Render publication-grade LaTeX table with booktabs formatting."""
        buf = io.StringIO()
        buf.write("\\begin{table*}[t]\n")
        buf.write("\\centering\n")
        buf.write(f"\\caption{{{caption}}}\n")
        buf.write(f"\\label{{{label}}}\n")
        buf.write("\\resizebox{\\textwidth}{!}{\n")
        buf.write("\\begin{tabular}{l ccccc c}\n")
        buf.write("\\toprule\n")
        buf.write(
            "\\textbf{Architectural Configuration} & "
            "\\textbf{Success Rate (\\%)} & "
            "\\textbf{Plan Acc (\\%)} & "
            "\\textbf{Tool F1} & "
            "\\textbf{Latency (s)} & "
            "\\textbf{Recovery (\\%)} & "
            "\\textbf{Safety Viol.} \\\\\n"
        )
        buf.write("\\midrule\n")

        for idx, s in enumerate(summaries):
            is_ours = idx == len(summaries) - 1
            config_name = s.configuration
            if is_ours:
                config_str = f"\\textbf{{{config_name}}} \\textit{{(Ours)}}"
                sr_str = f"\\textbf{{{s.task_success_rate:.1f}}}"
                pa_str = f"\\textbf{{{s.planning_accuracy:.1f}}}"
                f1_str = f"\\textbf{{{s.tool_selection_f1:.2f}}}"
                lat_str = f"\\textbf{{{s.avg_latency_ms / 1000.0:.2f}}}"
                frr_str = f"\\textbf{{{s.fault_recovery_rate:.1f}}}"
                viol_str = f"\\textbf{{{s.safety_violations}}}"
            else:
                config_str = config_name
                sr_str = f"{s.task_success_rate:.1f}"
                pa_str = f"{s.planning_accuracy:.1f}"
                f1_str = f"{s.tool_selection_f1:.2f}"
                lat_str = f"{s.avg_latency_ms / 1000.0:.2f}"
                frr_str = f"{s.fault_recovery_rate:.1f}"
                viol_str = f"{s.safety_violations}"

            buf.write(
                f"{config_str} & {sr_str} & {pa_str} & {f1_str} & {lat_str} & {frr_str} & {viol_str} \\\\\n"
            )

        buf.write("\\bottomrule\n")
        buf.write("\\end{tabular}\n")
        buf.write("}\n")
        buf.write("\\end{table*}\n")
        return buf.getvalue()

    @staticmethod
    def to_csv(summaries: list[AblationSummary]) -> str:
        """Render aggregated ablation summaries as standard CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "configuration",
            "task_success_rate_percent",
            "planning_accuracy_percent",
            "tool_selection_f1",
            "avg_latency_ms",
            "avg_latency_sec",
            "fault_recovery_rate_percent",
            "safety_violations",
            "avg_cost_per_task_usd",
            "tasks_evaluated",
        ])

        for s in summaries:
            writer.writerow([
                s.configuration,
                s.task_success_rate,
                s.planning_accuracy,
                s.tool_selection_f1,
                s.avg_latency_ms,
                round(s.avg_latency_ms / 1000.0, 2),
                s.fault_recovery_rate,
                s.safety_violations,
                s.avg_cost_per_task,
                s.tasks_evaluated,
            ])

        return output.getvalue()

    @staticmethod
    def results_to_csv(results: list[TaskRunResult]) -> str:
        """Render granular per-task run results as CSV for detailed plotting."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "task_id",
            "config_name",
            "success",
            "planning_accuracy",
            "tool_selection_f1",
            "latency_ms",
            "prompt_tokens",
            "completion_tokens",
            "cost_usd",
            "safety_violations",
            "recovery_successful",
            "rollback_verified",
        ])

        for r in results:
            writer.writerow([
                r.task_id,
                r.config_name,
                r.success,
                r.planning_accuracy,
                r.tool_selection_f1,
                r.latency_ms,
                r.prompt_tokens,
                r.completion_tokens,
                r.cost_usd,
                r.safety_violations,
                r.recovery_successful if r.recovery_successful is not None else "N/A",
                r.rollback_verified,
            ])

        return output.getvalue()
