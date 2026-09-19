'use client';

import { cn } from '@/lib/utils';

const STEPS = [
  {
    num: '01',
    title: 'Incident Detection',
    desc: 'CloudWatch detects abnormal conditions: CPU spikes, container crashes, latency anomalies, 5xx error surges. Alarms trigger the orchestration pipeline.',
    agent: 'CloudWatch',
    color: 'border-sre-error/40',
  },
  {
    num: '02',
    title: 'Orchestration',
    desc: 'The SRE Orchestrator, built on AWS Strands Agents SDK, receives the incident. It retrieves historical context from AgentCore Memory and decides which specialists to engage.',
    agent: 'SREOrchestrator',
    color: 'border-sre-accent/40',
  },
  {
    num: '03',
    title: 'Investigation',
    desc: 'The Log Analyst agent examines CloudWatch logs, metrics, and resource health. It identifies the probable root cause with supporting evidence and a confidence score.',
    agent: 'LogAnalyst',
    color: 'border-sre-info/40',
  },
  {
    num: '04',
    title: 'Remediation Decision',
    desc: 'The Remediator evaluates safe actions from an approved allowlist. It proposes a specific remediation with risk assessment. Arbitrary commands are never allowed.',
    agent: 'Remediator',
    color: 'border-sre-warning/40',
  },
  {
    num: '05',
    title: 'Safe Execution',
    desc: 'Approved remediations execute through explicit Boto3 functions. A safety layer validates every action before it touches infrastructure. Dry-run and simulation modes prevent unintended changes.',
    agent: 'Safety Layer',
    color: 'border-sre-warning/40',
  },
  {
    num: '06',
    title: 'Verification',
    desc: 'The Verifier agent runs comprehensive health checks: CPU, memory, error rates, container restarts, latency, and alarm states. It confirms actual recovery, not just action completion.',
    agent: 'Verifier',
    color: 'border-sre-success/40',
  },
  {
    num: '07',
    title: 'Memory & Learning',
    desc: 'AgentCore Memory stores the incident post-mortem: root cause, remediation, outcome, and lessons learned. Future incidents benefit from this accumulated knowledge.',
    agent: 'AgentCore Memory',
    color: 'border-purple-400/40',
  },
  {
    num: '08',
    title: 'Observability',
    desc: 'OpenTelemetry captures the full agent execution trace. Every decision, tool call, and API interaction is recorded with timing and metadata for X-Ray and CloudWatch visualization.',
    agent: 'OpenTelemetry',
    color: 'border-sre-text-dim/40',
  },
];

export default function ArchitecturePage() {
  return (
    <div className="p-6 sre-grid-bg min-h-screen">
      <h1 className="text-xl font-semibold text-sre-text-bright tracking-tight mb-2">
        How It Works
      </h1>
      <p className="text-sm text-sre-text-dim max-w-2xl mb-8">
        A multi-agent system that goes beyond alerting. It detects what broke, investigates why,
        proposes a safe fix, executes it, verifies recovery, and remembers the lesson.
      </p>

      <div className="sre-glow-line mb-8" />

      {/* Architecture Diagram */}
      <div className="bg-sre-surface border border-sre-border rounded-lg p-6 mb-10 max-w-3xl mx-auto">
        <pre className="text-xs font-mono text-sre-text-dim leading-relaxed overflow-x-auto">
{`                 ┌───────────────────────┐
                 │    Web Dashboard      │
                 │    Next.js / React    │
                 └──────────┬────────────┘
                            │
                            ▼
                 ┌───────────────────────┐
                 │     FastAPI API       │
                 │   SRE Control Plane   │
                 └──────────┬────────────┘
                            │
                            ▼
               ┌─────────────────────────┐
               │    SRE Orchestrator     │
               │     Strands Agent       │
               └────────────┬────────────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
           ▼                ▼                ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ Log Analyst  │ │ Remediator   │ │  Verifier    │
   │    Agent     │ │    Agent     │ │    Agent     │
   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
                ┌──────────▼──────────┐
                │    AWS Services     │
                │  CloudWatch · ECS   │
                │  SQS · AutoScaling  │
                └──────────┬──────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
     AgentCore Memory           OTEL / X-Ray
     Incident History           Agent Traces`}
        </pre>
      </div>

      {/* Pipeline Steps */}
      <div className="max-w-3xl mx-auto space-y-4">
        {STEPS.map((step) => (
          <div
            key={step.num}
            className={cn(
              'bg-sre-surface border-l-2 rounded-r-lg px-6 py-5',
              step.color,
            )}
          >
            <div className="flex items-baseline gap-4 mb-2">
              <span className="text-lg font-mono text-sre-text-dim font-light">
                {step.num}
              </span>
              <h3 className="text-sm font-semibold text-sre-text-bright">{step.title}</h3>
              <span className="text-[10px] font-mono text-sre-text-dim ml-auto">
                {step.agent}
              </span>
            </div>
            <p className="text-sm text-sre-text leading-relaxed pl-10">{step.desc}</p>
          </div>
        ))}
      </div>

      {/* Tech Stack */}
      <div className="max-w-3xl mx-auto mt-10">
        <h2 className="text-sm font-medium text-sre-text-dim mb-4">Technology Stack</h2>
        <div className="grid grid-cols-3 gap-3">
          <TechCard title="Agents" items={['AWS Strands SDK', 'Amazon Bedrock', 'Multi-agent supervisor']} />
          <TechCard title="Memory" items={['AgentCore Memory', 'Semantic retrieval', 'Post-mortem storage']} />
          <TechCard title="Observability" items={['OpenTelemetry', 'AWS X-Ray', 'CloudWatch']} />
          <TechCard title="Backend" items={['Python 3.11+', 'FastAPI', 'Pydantic v2']} />
          <TechCard title="Frontend" items={['Next.js 14', 'TypeScript', 'Tailwind CSS']} />
          <TechCard title="Safety" items={['Action allowlist', 'Dry-run mode', 'Approval flow']} />
        </div>
      </div>
    </div>
  );
}

function TechCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="bg-sre-surface border border-sre-border rounded-lg p-4">
      <h3 className="text-xs font-mono text-sre-accent mb-2">{title}</h3>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item} className="text-xs text-sre-text-dim">{item}</li>
        ))}
      </ul>
    </div>
  );
}
