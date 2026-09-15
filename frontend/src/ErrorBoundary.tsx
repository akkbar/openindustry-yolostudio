import { Component, type ErrorInfo, type ReactNode } from 'react';
import { en } from './locales/en';

export default class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error(en.crashTitle, error, info.componentStack); }
  render() {
    if (this.state.failed) return <main className="crash-screen"><h1>{en.crashTitle}</h1><p>{en.crashDetail}</p><button className="primary-button" onClick={() => window.location.reload()}>{en.reload}</button></main>;
    return this.props.children;
  }
}
