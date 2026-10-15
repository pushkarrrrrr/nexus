import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("NEXUS Ambient uncaught render error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="ambient-container">
          <div className="capsule" style={{ padding: "20px" }}>
            <div style={{ color: "#f87171", fontWeight: "bold", fontSize: "14px", marginBottom: "8px" }}>
              ✦ NEXUS Ambient Recovery
            </div>
            <div style={{ color: "#cbd5e1", fontSize: "12px", fontFamily: "monospace", marginBottom: "14px" }}>
              {this.state.error?.message || "An unexpected error occurred during rendering."}
            </div>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="btn-primary"
              style={{ alignSelf: "flex-start" }}
            >
              Reload Ambient Shell
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);

