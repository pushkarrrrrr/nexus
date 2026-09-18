export interface SessionItem {
  id: string;
  surface: "dashboard" | "ambient";
  title: string;
  created_at: string;
  message_count: number;
  active_task?: string;
  os_context: {
    active_app: string;
    window_title: string;
    cwd: string;
  };
}

export const mockSessions: SessionItem[] = [
  {
    id: "sess_01H9A1K4001",
    surface: "ambient",
    title: "Refactor auth middleware to Bearer tokens",
    created_at: "2026-09-18 18:30:12",
    message_count: 8,
    active_task: "Refactor Auth Middleware",
    os_context: {
      active_app: "com.microsoft.VSCode",
      window_title: "nexus — services/api/middleware.py",
      cwd: "/Users/apple/coding/nexus",
    },
  },
  {
    id: "sess_01H9A2M9002",
    surface: "dashboard",
    title: "Database schema migration & verification",
    created_at: "2026-09-18 17:45:00",
    message_count: 14,
    active_task: "Run Alembic Migrations",
    os_context: {
      active_app: "com.apple.Terminal",
      window_title: "apple@MacBook: ~/coding/nexus",
      cwd: "/Users/apple/coding/nexus/infra/database",
    },
  },
  {
    id: "sess_01H9A3X8003",
    surface: "ambient",
    title: "Index arXiv research papers on agentic DAGs",
    created_at: "2026-09-18 16:15:30",
    message_count: 5,
    os_context: {
      active_app: "com.google.Chrome",
      window_title: "ArXiv:2408.01234 Autonomous Agents",
      cwd: "/Users/apple/Downloads",
    },
  },
  {
    id: "sess_01H9A4P2004",
    surface: "dashboard",
    title: "Audit and rollback test file modifications",
    created_at: "2026-09-18 15:00:22",
    message_count: 6,
    os_context: {
      active_app: "com.apple.finder",
      window_title: "nexus",
      cwd: "/Users/apple/coding/nexus",
    },
  },
];
