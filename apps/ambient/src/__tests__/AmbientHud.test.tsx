import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ContextPill } from "../components/ContextPill";
import { PlanningView } from "../components/PlanningView";
import { InlineApprovalModal } from "../components/InlineApprovalModal";
import { ToolActivityPulse } from "../components/ToolActivityPulse";
import { ResultView } from "../components/ResultView";
import type { AmbientContextState, PlanStep, ApprovalRequestRecord } from "@nexus/types";

describe("AmbientHud Component Suite", () => {
  describe("ContextPill", () => {
    it("renders fallback when context is null and triggers refresh on click", () => {
      const onRefresh = vi.fn();
      const onToggle = vi.fn();

      render(
        <ContextPill
          context={null}
          attached={true}
          onToggleAttached={onToggle}
          onRefresh={onRefresh}
        />
      );

      const fallback = screen.getByText(/No Context/i);
      expect(fallback).toBeInTheDocument();

      fireEvent.click(fallback);
      expect(onRefresh).toHaveBeenCalledTimes(1);
    });

    it("renders appName and windowTitle when context is present", () => {
      const context: AmbientContextState = {
        appName: "VSCode",
        windowTitle: "nexus/App.tsx",
        capturedAt: new Date().toISOString(),
      };
      const onToggle = vi.fn();

      render(
        <ContextPill
          context={context}
          attached={true}
          onToggleAttached={onToggle}
          onRefresh={vi.fn()}
        />
      );

      expect(screen.getByText("VSCode: nexus/App.tsx")).toBeInTheDocument();
      expect(screen.getByText("●")).toBeInTheDocument();
    });

    it("toggles attached state on click", () => {
      const context: AmbientContextState = {
        appName: "Terminal",
        windowTitle: "bash",
        capturedAt: new Date().toISOString(),
      };
      const onToggle = vi.fn();

      const { rerender } = render(
        <ContextPill
          context={context}
          attached={true}
          onToggleAttached={onToggle}
          onRefresh={vi.fn()}
        />
      );

      const pill = screen.getByText("Terminal: bash");
      fireEvent.click(pill);
      expect(onToggle).toHaveBeenCalledTimes(1);

      rerender(
        <ContextPill
          context={context}
          attached={false}
          onToggleAttached={onToggle}
          onRefresh={vi.fn()}
        />
      );
      expect(screen.getByText("○")).toBeInTheDocument();
    });

    it("renders selection pill and triggers capture callback", () => {
      const context: AmbientContextState = {
        appName: "Safari",
        windowTitle: "Apple Developer",
        capturedAt: new Date().toISOString(),
      };
      const onCaptureSelection = vi.fn();

      const { rerender } = render(
        <ContextPill
          context={context}
          attached={true}
          onToggleAttached={vi.fn()}
          onRefresh={vi.fn()}
          selectedText={null}
          onCaptureSelection={onCaptureSelection}
        />
      );

      const selBtn = screen.getByText("+ Selection");
      expect(selBtn).toBeInTheDocument();
      fireEvent.click(selBtn);
      expect(onCaptureSelection).toHaveBeenCalledTimes(1);

      rerender(
        <ContextPill
          context={context}
          attached={true}
          onToggleAttached={vi.fn()}
          onRefresh={vi.fn()}
          selectedText="hello world from test"
          onCaptureSelection={onCaptureSelection}
        />
      );

      expect(screen.getByText(/Selection \(hello world from\.\.\.\)/)).toBeInTheDocument();
    });
  });

  describe("PlanningView", () => {
    it("renders placeholder when steps are empty", () => {
      render(<PlanningView steps={[]} />);
      expect(screen.getByText(/Decomposing task into DAG execution steps\.\.\./i)).toBeInTheDocument();
    });

    it("renders execution DAG steps with tools and assigned agents", () => {
      const steps: PlanStep[] = [
        {
          id: "step-1",
          description: "Read configuration file",
          status: "completed",
          required_tools: ["filesystem_read"],
          assigned_agent: "researcher",
          dependencies: [],
        },
        {
          id: "step-2",
          description: "Apply code modifications",
          status: "running",
          required_tools: ["file_edit"],
          assigned_agent: "coder",
          dependencies: ["step-1"],
        },
        {
          id: "step-3",
          description: "Run test suite",
          status: "awaiting_approval",
          required_tools: ["terminal_execute"],
          dependencies: ["step-2"],
        },
      ];

      render(<PlanningView steps={steps} />);

      expect(screen.getByText(/Execution DAG \(1\/3\)/i)).toBeInTheDocument();
      expect(screen.getByText("Read configuration file")).toBeInTheDocument();
      expect(screen.getByText("Apply code modifications")).toBeInTheDocument();
      expect(screen.getByText("Run test suite")).toBeInTheDocument();
      expect(screen.getByText("filesystem_read")).toBeInTheDocument();
      expect(screen.getByText("@researcher")).toBeInTheDocument();
      expect(screen.getByText("@coder")).toBeInTheDocument();
    });
  });

  describe("InlineApprovalModal", () => {
    const mockApproval: ApprovalRequestRecord = {
      id: "appr-123",
      user_id: "user-1",
      task_id: "task-1",
      step_id: "step-2",
      capability_name: "file_edit",
      action_category: "MODIFY",
      parameters: {},
      risk_level: "HIGH",
      reason: "Modifying production configuration in config.yaml",
      diff_preview: "--- config.yaml\n+++ config.yaml\n- debug: true\n+ debug: false",
      affected_resources: ["/etc/nexus/config.yaml"],
      is_reversible: true,
      status: "PENDING",
      created_at: new Date().toISOString(),
    };

    it("renders risk badges, diff lines, and targets properly", () => {
      const onResolve = vi.fn();
      render(<InlineApprovalModal approval={mockApproval} onResolve={onResolve} />);

      expect(screen.getByText("Authorization Required")).toBeInTheDocument();
      expect(screen.getByText("HIGH RISK")).toBeInTheDocument();
      expect(screen.getByText("↺ Reversible")).toBeInTheDocument();
      expect(screen.getByText("file_edit")).toBeInTheDocument();
      expect(screen.getByText(/\/etc\/nexus\/config\.yaml/)).toBeInTheDocument();
      expect(screen.getByText(/Modifying production configuration/)).toBeInTheDocument();
      expect(screen.getByText("- debug: true")).toBeInTheDocument();
      expect(screen.getByText("+ debug: false")).toBeInTheDocument();
    });

    it("dispatches resolution decisions", () => {
      const onResolve = vi.fn();
      render(<InlineApprovalModal approval={mockApproval} onResolve={onResolve} />);

      fireEvent.click(screen.getByRole("button", { name: /Deny \(Esc\)/i }));
      expect(onResolve).toHaveBeenCalledWith("deny");

      fireEvent.click(screen.getByRole("button", { name: /Approve Session/i }));
      expect(onResolve).toHaveBeenCalledWith("approve_session");

      fireEvent.click(screen.getByRole("button", { name: /Approve Once/i }));
      expect(onResolve).toHaveBeenCalledWith("approve_once");
    });
  });

  describe("ToolActivityPulse", () => {
    it("renders active tool and target details", () => {
      render(
        <ToolActivityPulse
          activity={{
            tool: "terminal_execute",
            target: "npm test",
            status: "running",
          }}
        />
      );

      expect(screen.getByText("terminal_execute")).toBeInTheDocument();
      expect(screen.getByText("running...")).toBeInTheDocument();
      expect(screen.getByText("target: npm test")).toBeInTheDocument();
    });
  });

  describe("ResultView", () => {
    it("renders result content, handles copy and submit follow-up", () => {
      const onCopy = vi.fn();
      const onFollowUp = vi.fn();
      const onNewQuery = vi.fn();

      render(
        <ResultView
          content="All 134 tests successfully verified."
          onCopy={onCopy}
          onFollowUp={onFollowUp}
          onNewQuery={onNewQuery}
        />
      );

      expect(screen.getByText("All 134 tests successfully verified.")).toBeInTheDocument();

      // Copy
      const copyBtn = screen.getByRole("button", { name: /Copy/i });
      fireEvent.click(copyBtn);
      expect(onCopy).toHaveBeenCalledTimes(1);
      expect(screen.getByText("✓ Copied")).toBeInTheDocument();

      // New Query
      const newQueryBtn = screen.getByRole("button", { name: /New Query/i });
      fireEvent.click(newQueryBtn);
      expect(onNewQuery).toHaveBeenCalledTimes(1);

      // Follow-up form
      const input = screen.getByPlaceholderText(/Ask a follow-up query\.\.\./i);
      const sendBtn = screen.getByRole("button", { name: /Send/i });

      expect(sendBtn).toBeDisabled();
      fireEvent.change(input, { target: { value: "Can you run ruff check too?" } });
      expect(sendBtn).not.toBeDisabled();

      fireEvent.click(sendBtn);
      expect(onFollowUp).toHaveBeenCalledWith("Can you run ruff check too?");
    });
  });
});
