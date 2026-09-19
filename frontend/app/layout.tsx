import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Autonomous SRE | Self-Healing Cloud Swarm',
  description: 'AI agents that investigate, remediate, and verify cloud incidents autonomously.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-sre-bg text-sre-text antialiased">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}

function Sidebar() {
  const links = [
    { href: '/', label: 'Dashboard', icon: '◉' },
    { href: '/#incidents', label: 'Incidents', icon: '⚡' },
    { href: '/architecture', label: 'Architecture', icon: '⬡' },
    { href: '/observability', label: 'Observability', icon: '◎' },
    { href: '/memory', label: 'Memory', icon: '◈' },
  ];

  return (
    <nav className="w-56 border-r border-sre-border bg-sre-surface flex flex-col shrink-0">
      <div className="p-5 border-b border-sre-border">
        <div className="flex items-center gap-2">
          <span className="text-sre-accent text-lg font-mono font-semibold">◈</span>
          <div>
            <div className="text-sm font-semibold text-sre-text-bright tracking-tight">
              Autonomous SRE
            </div>
            <div className="text-[10px] font-mono text-sre-text-dim tracking-wider uppercase">
              Self-Healing Swarm
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 py-3">
        {links.map((link) => (
          <a
            key={link.href}
            href={link.href}
            className="flex items-center gap-3 px-5 py-2.5 text-sm text-sre-text-dim hover:text-sre-text-bright hover:bg-sre-raised/50 transition-colors"
          >
            <span className="text-xs font-mono opacity-60">{link.icon}</span>
            {link.label}
          </a>
        ))}
      </div>

      <div className="p-4 border-t border-sre-border">
        <div className="flex items-center gap-2 text-[11px] font-mono text-sre-text-dim">
          <span className="w-1.5 h-1.5 rounded-full bg-sre-accent status-pulse" />
          Simulation Mode
        </div>
      </div>
    </nav>
  );
}
