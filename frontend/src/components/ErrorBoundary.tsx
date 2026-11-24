import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public override state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  public override render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="card" style={{ margin: "2rem auto", maxWidth: 600 }}>
          <h2 className="card-title">Something went wrong</h2>
          <p style={{ color: "var(--text-muted)", marginBottom: "1rem" }}>
            An unexpected error occurred while rendering this view.
          </p>
          <div className="code-block" style={{ color: "var(--danger)" }}>
            {this.state.error?.message || "Unknown error"}
          </div>
          <button
            className="btn btn-secondary"
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            style={{ marginTop: "1rem" }}
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
