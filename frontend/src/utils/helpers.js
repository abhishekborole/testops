import { VM } from '../data/constants.js';

export function calcStats(tests) {
  const total = tests.length;
  const passed = tests.filter(t => t.status === 'passed').length;
  const failed = tests.filter(t => t.status === 'failed').length;
  const running = tests.filter(t => t.status === 'running').length;
  const pending = tests.filter(t => t.status === 'pending').length;
  const rate = total > 0 ? Math.round((passed / total) * 100) : 0;

  let verdict;
  if (running > 0 || pending === total) verdict = 'running';
  else if (rate >= 95) verdict = 'ready';
  else if (rate >= 75) verdict = 'at-risk';
  else verdict = 'not-ready';

  return { total, passed, failed, running, pending, rate, verdict };
}

export function mkId() {
  const letters = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
  const digits = '0123456789';
  const part1 = Array.from({ length: 5 }, () => letters[Math.floor(Math.random() * letters.length)]).join('');
  const part2 = Array.from({ length: 3 }, () => digits[Math.floor(Math.random() * digits.length)]).join('');
  return `PRT-${part1}-${part2}`;
}

export function fakeLog(name, ok) {
  const ts = () => {
    const now = new Date();
    return `${now.toISOString().split('T')[1].split('.')[0]}`;
  };
  const lines = [];
  lines.push(`[${ts()}] INFO  Starting test: ${name}`);
  lines.push(`[${ts()}] INFO  Establishing connection to cluster API...`);
  lines.push(`[${ts()}] DEBUG Sending probe request`);
  if (ok) {
    lines.push(`[${ts()}] INFO  Response received: 200 OK`);
    lines.push(`[${ts()}] INFO  Validating response payload...`);
    lines.push(`[${ts()}] INFO  Assertion check: PASS`);
    lines.push(`[${ts()}] INFO  Cleanup completed`);
    lines.push(`[${ts()}] INFO  Test PASSED ✓`);
  } else {
    lines.push(`[${ts()}] WARN  Response timeout after 5000ms`);
    lines.push(`[${ts()}] ERROR Expected status 200, got 503`);
    lines.push(`[${ts()}] ERROR Assertion failed: service unavailable`);
    lines.push(`[${ts()}] INFO  Collecting diagnostic data...`);
    lines.push(`[${ts()}] INFO  Test FAILED ✗`);
  }
  return lines.join('\n');
}

export function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function md(t) {
  if (!t) return '';
  return t
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>');
}

export function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.round((ms % 60000) / 1000);
  return `${m}m ${s}s`;
}

export function getVerdictInfo(verdict) {
  return VM[verdict] || VM['not-ready'];
}

export function timeAgo(dateStr) {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  if (diff < 60000) return 'just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return `${Math.floor(diff / 86400000)}d ago`;
}
