import { Component, type ErrorInfo, type ReactNode } from "react";

/** Keeps one crashing panel from taking down the whole station UI. */
export class ErrorBoundary extends Component<{ name: string; children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error(`[${this.props.name}]`, error, info.componentStack); }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="status" className="m-2 rounded-xl border border-critical/50 bg-surface p-4 text-sm">
        <p className="font-semibold text-text">This panel failed</p>
        <p className="mt-1 text-text-2">{this.props.name}: {this.state.error.message}</p>
        <button type="button" onClick={() => this.setState({ error: null })}
          className="mt-3 rounded-lg border border-line bg-surface-2 px-3 py-1.5 font-medium hover:bg-surface-3">
          Reload panel
        </button>
      </div>
    );
  }
}
