/**
 * NEXUS Design System Tokens
 * Unified color palette, glassmorphism, and status indicators.
 */

export const nexusColors = {
  bg: {
    base: '#0a0d14',
    surface: '#111726',
    surfaceSubtle: '#182138',
    card: 'rgba(17, 23, 38, 0.75)',
  },
  border: {
    subtle: 'rgba(255, 255, 255, 0.08)',
    active: 'rgba(56, 189, 248, 0.4)',
    glow: 'rgba(56, 189, 248, 0.2)',
  },
  text: {
    primary: '#f8fafc',
    secondary: '#94a3b8',
    muted: '#64748b',
  },
  status: {
    online: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#38bdf8',
    idle: '#64748b',
  },
  risk: {
    low: '#10b981',
    medium: '#f59e0b',
    high: '#f97316',
    critical: '#ef4444',
  }
} as const;
