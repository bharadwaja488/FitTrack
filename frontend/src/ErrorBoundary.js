import React, { Component } from 'react'

const fallbackCopy = {
  title: 'FitTrack hit a rendering problem',
  description: 'Your account data is safe. Try rendering the page again, or reload FitTrack if the problem continues.',
  retry: 'Try again',
  reload: 'Reload FitTrack',
}

export default class ErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    // Component stacks identify the failing UI without logging exception text,
    // props, response bodies, account data, or session material.
    const safeErrorNames = new Set(['Error', 'TypeError', 'ReferenceError', 'RangeError', 'SyntaxError', 'URIError', 'EvalError'])
    const errorName = safeErrorNames.has(error?.name) ? error.name : 'Error'
    const componentStack = typeof info?.componentStack === 'string'
      ? info.componentStack.slice(0, 4000)
      : 'Component stack unavailable'
    console.error('[FitTrack] React rendering failure', { errorName, componentStack })
  }

  retry = () => this.setState({ hasError: false })

  render() {
    if (!this.state.hasError) return this.props.children
    return React.createElement(
      'main',
      { className: 'render-error-screen', role: 'alert', 'aria-labelledby': 'render-error-title' },
      React.createElement('div', { className: 'render-error-card' },
        React.createElement('span', { className: 'eyebrow' }, 'FITTRACK'),
        React.createElement('h1', { id: 'render-error-title' }, fallbackCopy.title),
        React.createElement('p', null, fallbackCopy.description),
        React.createElement('div', { className: 'render-error-actions' },
          React.createElement('button', { className: 'button button-primary', onClick: this.retry }, fallbackCopy.retry),
          React.createElement('button', {
            className: 'button button-ghost',
            onClick: () => {
              if (typeof window !== 'undefined' && typeof window.location?.reload === 'function') window.location.reload()
            },
          }, fallbackCopy.reload),
        ),
      ),
    )
  }
}
