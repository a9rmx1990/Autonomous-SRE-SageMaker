'use client';

import { useState, useEffect } from 'react';
import { getIncidents, getTrace, type Incident, type IncidentEvent } from '@/lib/api';
import { formatTimestamp, agentColor, cn } from '@/lib/utils';

export default function ObservabilityPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [traceEvents, setTraceEvents] = useState<IncidentEvent[]>([]);
  const [traceId, setTraceId] = useState<string | null>(null);

  useEffect(() => {
    getIncidents().then(setIncidents).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    getTrace(selectedId).then((data) => {
      setTraceEvents(data.events);
      setTraceId(data.trace_id);
    }).catch(() => {});
  }, [selectedId]);

  // Auto-select first resolved incident
  useEffect(() => {
    if (!selectedId && incidents.length > 0) {
      const resolved = incidents.find((i) => i.status === 'resolved');
      setSelectedId(resolved?.id || incidents[0].id);
    }
  }, [incidents, selectedId]);

  return (
    <div className="p-6 sre-grid-bg min-h-screen">
      <h1 className="text-xl font-semibold text-sre-text-bright tracking-tight mb-2">
        Observability
      </h1>
      <p className="text-sm text-sre-text-dim mb-6">
        Agent execution traces, tool calls, and timing data.
      </p>

      <div className="sre-glow-line mb-6" />

      {/* Pipeline explanation */}
      <div className="bg-sre-surface border border-sre-border rounded-lg p-4 mb-6 max-w-2xl">
        <h3 className="text-xs font-mono text-sre-text-dim mb-3">Trace Pipeline</h3>
        <div className="flex items-center gap-2 text-xs font-mono text-sre-text-dim flex-wrap">
          <span className="text-sre-text">Agent Execution</span>
          <span className="text-sre-border">→</span>
          <span className="text-sre-text">OpenTelemetry Spans</span>
          <span className="text-sre-border">→</span>
          <span className="text-sre-text">OTLP Exporter</span>
          <span className="text-sre-border">→</span>
          <span className="text-sre-text">AWS X-Ray</span>
          <span className="text-sre-border">→</span>
          <span className="text-sre-text">CloudWatch</span>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {/* Incident selector */}
        <div className="col-span-1">
          <h3 className="text-xs font-mono text-sre-text-dim mb-3">Select Incident</h3>
          {incidents.length === 0 ? (
            <p className="text-xs text-sre-text-dim">
              No incidents yet. Run a simulation from the dashboard.
            </p>
          ) : (
            <div className="space-y-1.5">
              {incidents.map((inc, idx) => (
                <button
                  key={inc.id || `inc-${idx}`}
                  onClick={() => setSelectedId(inc.id)}
                  className={cn(
                    'w-full text-left px-3 py-2 rounded-md border text-xs font-mono transition-colors',
                    selectedId === inc.id
                      ? 'border-sre-accent/40 bg-sre-accent/5 text-sre-text-bright'
                      : 'border-sre-border bg-sre-surface text-sre-text-dim hover:border-sre-border-light',
                  )}
                >
                  <div className="truncate">{inc.title}</div>
                  <div className="text-[10px] mt-0.5 text-sre-text-dim">
                    {inc.id} / {inc.status}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Trace timeline */}
        <div className="col-span-3">
          {traceId && (
            <div className="text-xs font-mono text-sre-text-dim mb-4">
              Trace ID: <span className="text-sre-accent">{traceId}</span>
            </div>
          )}

          {traceEvents.length === 0 ? (
            <div className="bg-sre-surface border border-sre-border rounded-lg p-8 text-center">
              <p className="text-sm text-sre-text-dim">
                Select an incident to view its execution trace.
              </p>
            </div>
          ) : (
            <div className="space-y-0">
              {traceEvents.map((event, idx) => {
                const prev = idx > 0 ? traceEvents[idx - 1] : null;
                const duration = prev
                  ? new Date(event.timestamp).getTime() - new Date(prev.timestamp).getTime()
                  : 0;

                return (
                  <div
                    key={event.id}
                    className="flex items-start gap-4 group"
                  >
                    {/* Timeline connector */}
                    <div className="flex flex-col items-center w-4 pt-1">
                      <div
                        className={cn(
                          'w-2 h-2 rounded-full',
                          event.event_type === 'error'
                            ? 'bg-sre-error'
                            : event.event_type === 'system' &&
                                event.message.toLowerCase().includes('resolved')
                              ? 'bg-sre-success'
                              : 'bg-sre-accent/60',
                        )}
                      />
                      {idx < traceEvents.length - 1 && (
                        <div className="w-px flex-1 bg-sre-border min-h-[20px]" />
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 pb-3 min-w-0">
                      <div className="flex items-baseline gap-3">
                        <span className="text-[11px] font-mono text-sre-text-dim">
                          {formatTimestamp(event.timestamp)}
                        </span>
                        <span className={cn('text-[11px] font-mono', agentColor(event.agent))}>
                          {event.agent}
                        </span>
                        {duration > 0 && (
                          <span className="text-[10px] font-mono text-sre-text-dim ml-auto">
                            +{duration}ms
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-sre-text mt-0.5 leading-relaxed">
                        {event.message}
                      </p>
                      {event.data && Object.keys(event.data).length > 0 && (
                        <details className="mt-1.5">
                          <summary className="text-[10px] font-mono text-sre-text-dim cursor-pointer hover:text-sre-text">
                            metadata
                          </summary>
                          <pre className="text-[10px] font-mono text-sre-text-dim mt-1 bg-sre-raised rounded p-2 overflow-x-auto">
                            {JSON.stringify(event.data, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
