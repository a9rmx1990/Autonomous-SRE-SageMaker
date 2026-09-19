'use client';

import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useIncident } from '@/hooks/useIncident';
import {
  formatTimestamp,
  formatDuration,
  severityColor,
  statusColor,
  agentColor,
  cn,
} from '@/lib/utils';
import type { IncidentEvent, Incident } from '@/lib/api';

export default function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { incident, events, loading, error } = useIncident(id);

  if (loading) {
    return (
      <div className="p-8 sre-grid-bg min-h-screen flex items-center justify-center">
        <div className="text-sre-text-dim font-mono text-sm animate-pulse">Loading incident...</div>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="p-8 sre-grid-bg min-h-screen">
        <div className="border border-sre-error/30 bg-sre-error/5 rounded-lg p-6 max-w-xl mx-auto mt-20">
          <p className="text-sre-error text-sm">{error || 'Incident not found'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 sre-grid-bg min-h-screen">
      {/* Header */}
      <div className="mb-6">
        <a href="/" className="text-xs font-mono text-sre-text-dim hover:text-sre-accent transition-colors">
          ← Control Plane
        </a>
        <div className="flex items-center gap-3 mt-3">
          <StatusDot status={incident.status} />
          <h1 className="text-lg font-semibold text-sre-text-bright">{incident.title}</h1>
          {incident.simulation && (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sre-accent/10 text-sre-accent border border-sre-accent/20">
              SIMULATION
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 mt-2 text-xs font-mono text-sre-text-dim">
          <span className="text-sre-text">{incident.service}</span>
          <span className={severityColor(incident.severity)}>{incident.severity}</span>
          <span className={statusColor(incident.status)}>
            {incident.status.replace(/_/g, ' ')}
          </span>
          <span>{formatTimestamp(incident.created_at)}</span>
          {incident.duration_seconds && (
            <span>Duration: {formatDuration(incident.duration_seconds)}</span>
          )}
        </div>
      </div>

      <div className="sre-glow-line mb-6" />

      <div className="grid grid-cols-3 gap-6">
        {/* Left: Status Pipeline */}
        <div className="col-span-1">
          <IncidentPipeline status={incident.status} />

          {/* Agent Swarm Viz */}
          <div className="mt-6">
            <AgentSwarm activeAgent={getActiveAgent(events)} />
          </div>

          {/* Findings Summary */}
          {incident.findings && (
            <div className="mt-6 bg-sre-surface border border-sre-border rounded-lg p-4">
              <h3 className="text-xs font-mono text-sre-text-dim mb-3">Root Cause</h3>
              <p className="text-sm text-sre-text-bright leading-relaxed">
                {incident.findings.probable_root_cause}
              </p>
              <div className="mt-3 flex items-center gap-3 text-xs font-mono">
                <span className={severityColor(incident.findings.severity)}>
                  {incident.findings.severity}
                </span>
                <span className="text-sre-text-dim">
                  Confidence: {(incident.findings.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          )}

          {/* Remediation */}
          {incident.remediation && (
            <div className="mt-4 bg-sre-surface border border-sre-border rounded-lg p-4">
              <h3 className="text-xs font-mono text-sre-text-dim mb-3">Remediation</h3>
              <div className="space-y-2 text-xs font-mono">
                <Row label="Action" value={incident.remediation.action} />
                <Row label="Resource" value={incident.remediation.resource_id} />
                <Row label="Risk" value={incident.remediation.risk} />
                <Row label="Approved" value={incident.remediation.approved ? 'Yes' : 'Pending'} />
                <Row label="Executed" value={incident.remediation.executed ? 'Yes' : 'No'} />
              </div>
            </div>
          )}

          {/* Verification */}
          {incident.verification && (
            <div className="mt-4 bg-sre-surface border border-sre-border rounded-lg p-4">
              <h3 className="text-xs font-mono text-sre-text-dim mb-3">Verification</h3>
              <div className="space-y-1.5">
                {incident.verification.checks.map((check, i) => (
                  <div key={check.name || i} className="flex items-center justify-between text-xs font-mono">
                    <span className="text-sre-text-dim">{check.name}</span>
                    <span
                      className={
                        check.status === 'pass' ? 'text-sre-success' : 'text-sre-error'
                      }
                    >
                      {String(check.value)}
                      {check.unit ? ` ${check.unit}` : ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Post-Mortem & Memory */}
          {incident.post_mortem && (
            <div className="mt-4 bg-sre-surface border border-sre-border rounded-lg p-4">
              <h3 className="text-xs font-mono text-sre-text-dim mb-3">AgentCore Post-Mortem</h3>
              <div className="space-y-3 text-xs">
                {Boolean(incident.post_mortem.summary) && (
                  <p className="text-sm font-medium text-sre-text-bright">
                    {String(incident.post_mortem.summary)}
                  </p>
                )}
                {Boolean(incident.post_mortem.root_cause) && (
                  <div>
                    <span className="text-[10px] font-mono text-sre-error uppercase block mb-0.5 font-semibold">
                      Root Cause
                    </span>
                    <p className="text-sre-text-dim leading-relaxed">{String(incident.post_mortem.root_cause)}</p>
                  </div>
                )}
                {Boolean(incident.post_mortem.remediation) && (
                  <div>
                    <span className="text-[10px] font-mono text-sre-warning uppercase block mb-0.5 font-semibold">
                      Remediation
                    </span>
                    <p className="text-sre-text-dim leading-relaxed">{String(incident.post_mortem.remediation)}</p>
                  </div>
                )}
                {Boolean(incident.post_mortem.verification_result) && (
                  <div>
                    <span className="text-[10px] font-mono text-sre-success uppercase block mb-0.5 font-semibold">
                      Verification
                    </span>
                    <p className="text-sre-success leading-relaxed">{String(incident.post_mortem.verification_result)}</p>
                  </div>
                )}
                {Boolean(incident.post_mortem.metrics) && (
                  <div>
                    <span className="text-[10px] font-mono text-sre-text-dim uppercase block mb-0.5 font-semibold">
                      Metrics
                    </span>
                    <pre className="p-2 rounded bg-sre-raised text-[10px] font-mono text-sre-text-dim overflow-x-auto border border-sre-border/50">
                      {typeof incident.post_mortem.metrics === 'object'
                        ? JSON.stringify(incident.post_mortem.metrics, null, 2)
                        : String(incident.post_mortem.metrics)}
                    </pre>
                  </div>
                )}
                {Boolean(incident.post_mortem.lessons_learned) && (
                  <div className="p-2.5 rounded bg-sre-accent/5 border border-sre-accent/20">
                    <span className="text-[10px] font-mono text-sre-accent uppercase block mb-0.5 font-semibold">
                      Lessons Learned
                    </span>
                    <p className="text-sre-text-dim leading-relaxed">{String(incident.post_mortem.lessons_learned)}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right: Live Event Timeline */}
        <div className="col-span-2">
          <h2 className="text-sm font-medium text-sre-text-dim mb-4">Agent Activity</h2>
          <div className="space-y-1">
            <AnimatePresence initial={false}>
              {events.map((event, idx) => (
                <motion.div
                  key={event.id || `event-${idx}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <EventRow event={event} />
                </motion.div>
              ))}
            </AnimatePresence>

            {incident.status !== 'resolved' && incident.status !== 'failed' && (
              <div className="flex items-center gap-3 px-4 py-3 text-xs font-mono text-sre-text-dim">
                <span className="w-1.5 h-1.5 rounded-full bg-sre-accent status-pulse" />
                Processing...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function EventRow({ event }: { event: IncidentEvent }) {
  const isError = event.event_type === 'error';
  const displayMessage =
    typeof event.message === 'object' && event.message !== null
      ? JSON.stringify(event.message, null, 2)
      : String(event.message ?? '');

  return (
    <div
      className={cn(
        'flex gap-3 px-4 py-2.5 rounded-md border border-transparent',
        'hover:bg-sre-surface hover:border-sre-border transition-colors',
        isError && 'bg-sre-error/5 border-sre-error/20',
      )}
    >
      <span className="text-[11px] font-mono text-sre-text-dim whitespace-nowrap pt-0.5">
        {formatTimestamp(event.timestamp)}
      </span>
      <span
        className={cn(
          'text-[11px] font-mono whitespace-nowrap w-32 pt-0.5',
          agentColor(event.agent),
        )}
      >
        {event.agent}
      </span>
      <span className="text-sm text-sre-text leading-relaxed flex-1">{displayMessage}</span>
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === 'resolved'
      ? 'bg-sre-success'
      : status === 'failed'
        ? 'bg-sre-error'
        : 'bg-sre-warning';
  const pulse = status !== 'resolved' && status !== 'failed';
  return <span className={cn('w-2.5 h-2.5 rounded-full', color, pulse && 'status-pulse')} />;
}

const PIPELINE_STAGES = [
  { key: 'detected', label: 'Detected' },
  { key: 'investigating', label: 'Investigating' },
  { key: 'root_cause_found', label: 'Root Cause' },
  { key: 'remediating', label: 'Remediating' },
  { key: 'verifying', label: 'Verifying' },
  { key: 'resolved', label: 'Resolved' },
];

const STATUS_ORDER = PIPELINE_STAGES.map((s) => s.key);

function IncidentPipeline({ status }: { status: string }) {
  const currentIdx = STATUS_ORDER.indexOf(status);
  const failedIdx = status === 'failed' ? currentIdx : -1;

  return (
    <div className="bg-sre-surface border border-sre-border rounded-lg p-4">
      <h3 className="text-xs font-mono text-sre-text-dim mb-4">Pipeline</h3>
      <div className="space-y-0">
        {PIPELINE_STAGES.map((stage, i) => {
          const isActive = stage.key === status;
          const isComplete = currentIdx > i || status === 'resolved';
          const isFailed = status === 'failed' && i === currentIdx;

          return (
            <div key={stage.key} className="flex items-center gap-3">
              {/* Connector line */}
              <div className="flex flex-col items-center w-4">
                <div
                  className={cn(
                    'w-3 h-3 rounded-full border-2',
                    isComplete
                      ? 'bg-sre-accent border-sre-accent'
                      : isActive
                        ? 'border-sre-accent bg-sre-accent/30 status-pulse'
                        : isFailed
                          ? 'border-sre-error bg-sre-error/30'
                          : 'border-sre-border bg-transparent',
                  )}
                />
                {i < PIPELINE_STAGES.length - 1 && (
                  <div
                    className={cn(
                      'w-px h-5',
                      isComplete ? 'bg-sre-accent/50' : 'bg-sre-border',
                    )}
                  />
                )}
              </div>
              <span
                className={cn(
                  'text-xs font-mono py-1',
                  isComplete
                    ? 'text-sre-accent'
                    : isActive
                      ? 'text-sre-text-bright'
                      : 'text-sre-text-dim',
                )}
              >
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AgentSwarm({ activeAgent }: { activeAgent: string }) {
  const agents = [
    { id: 'SREOrchestrator', label: 'Orchestrator', sub: 'Supervisor' },
    { id: 'LogAnalyst', label: 'Log Analyst', sub: 'Investigation' },
    { id: 'Remediator', label: 'Remediator', sub: 'Remediation' },
    { id: 'Verifier', label: 'Verifier', sub: 'Validation' },
  ];

  return (
    <div className="bg-sre-surface border border-sre-border rounded-lg p-4">
      <h3 className="text-xs font-mono text-sre-text-dim mb-4">Agent Swarm</h3>
      <div className="relative">
        {/* Orchestrator centered */}
        <div className="flex justify-center mb-3">
          <AgentNode
            agent={agents[0]}
            isActive={activeAgent === agents[0].id}
          />
        </div>
        {/* Connection lines */}
        <div className="flex justify-center mb-1">
          <div className="flex items-end gap-8">
            <div className={cn('w-px h-4', activeAgent === 'LogAnalyst' ? 'bg-sre-info' : 'bg-sre-border')} />
            <div className={cn('w-px h-4', activeAgent === 'Remediator' ? 'bg-sre-warning' : 'bg-sre-border')} />
            <div className={cn('w-px h-4', activeAgent === 'Verifier' ? 'bg-sre-success' : 'bg-sre-border')} />
          </div>
        </div>
        {/* Specialist agents */}
        <div className="flex justify-center gap-3">
          {agents.slice(1).map((agent) => (
            <AgentNode
              key={agent.id}
              agent={agent}
              isActive={activeAgent === agent.id}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function AgentNode({
  agent,
  isActive,
}: {
  agent: { id: string; label: string; sub: string };
  isActive: boolean;
}) {
  return (
    <div
      className={cn(
        'px-3 py-2 rounded border text-center min-w-[80px] transition-all',
        isActive
          ? 'border-sre-accent/50 bg-sre-accent/10'
          : 'border-sre-border bg-sre-raised',
      )}
    >
      <div className={cn('text-[11px] font-mono', agentColor(agent.id))}>
        {agent.label}
      </div>
      <div className="text-[9px] text-sre-text-dim">{agent.sub}</div>
      {isActive && (
        <div className="mt-1">
          <span className="w-1 h-1 rounded-full bg-sre-accent inline-block status-pulse" />
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-sre-text-dim">{label}</span>
      <span className="text-sre-text">{value}</span>
    </div>
  );
}

function getActiveAgent(events: IncidentEvent[]): string {
  if (events.length === 0) return '';
  const last = events[events.length - 1];
  return last.agent;
}
