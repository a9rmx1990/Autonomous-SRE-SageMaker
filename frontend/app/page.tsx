'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  getDashboard,
  getIncidents,
  simulateIncident,
  type SystemHealth,
  type Incident,
} from '@/lib/api';
import {
  formatTimestamp,
  formatDuration,
  severityColor,
  statusColor,
  cn,
} from '@/lib/utils';

export default function Dashboard() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const refresh = useCallback(async () => {
    try {
      const [h, inc] = await Promise.all([getDashboard(), getIncidents()]);
      setHealth(h);
      setIncidents(inc);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to connect to backend');
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  const handleSimulate = async () => {
    setSimulating(true);
    try {
      const result = await simulateIncident();
      router.push(`/incidents/${result.incident_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Simulation failed');
    } finally {
      setSimulating(false);
    }
  };

  if (error && !health) {
    return (
      <div className="p-8 sre-grid-bg min-h-screen">
        <div className="max-w-2xl mx-auto mt-20">
          <div className="border border-sre-error/30 bg-sre-error/5 rounded-lg p-6">
            <h2 className="text-sre-error font-mono text-sm mb-2">Connection Error</h2>
            <p className="text-sre-text-dim text-sm">{error}</p>
            <p className="text-sre-text-dim text-xs mt-3 font-mono">
              Ensure the backend is running: uvicorn main:app --reload
            </p>
          </div>
        </div>
      </div>
    );
  }

  const systemStatusColor =
    health?.status === 'healthy'
      ? 'text-sre-success'
      : health?.status === 'degraded'
        ? 'text-sre-error'
        : 'text-sre-warning';

  return (
    <div className="p-6 sre-grid-bg min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold text-sre-text-bright tracking-tight">
            Control Plane
          </h1>
          <p className="text-xs font-mono text-sre-text-dim mt-1">
            Autonomous incident detection, investigation & remediation
          </p>
        </div>
        <button
          onClick={handleSimulate}
          disabled={simulating}
          className={cn(
            'px-4 py-2 text-sm font-medium rounded-md transition-all',
            'bg-sre-accent/10 text-sre-accent border border-sre-accent/30',
            'hover:bg-sre-accent/20 hover:border-sre-accent/50',
            'disabled:opacity-50 disabled:cursor-not-allowed',
          )}
        >
          {simulating ? 'Triggering...' : 'Simulate Payment API Incident'}
        </button>
      </div>

      <div className="sre-glow-line mb-8" />

      {/* Status Cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatusCard
          label="System Status"
          value={health?.status?.toUpperCase() || '...'}
          valueClass={systemStatusColor}
          pulse={health?.status !== 'healthy'}
        />
        <StatusCard
          label="Active Incidents"
          value={String(health?.active_incidents ?? 0)}
          valueClass={
            (health?.active_incidents ?? 0) > 0 ? 'text-sre-warning' : 'text-sre-text-bright'
          }
        />
        <StatusCard
          label="Resolved"
          value={String(health?.resolved_incidents ?? 0)}
          valueClass="text-sre-success"
        />
        <StatusCard
          label="Remediations"
          value={String(health?.total_remediations ?? 0)}
          valueClass="text-sre-info"
        />
      </div>

      {/* Services */}
      <div className="mb-8">
        <h2 className="text-sm font-medium text-sre-text-dim mb-3 tracking-wide">
          Service Health
        </h2>
        <div className="grid grid-cols-2 gap-3">
          {health?.services.map((svc) => (
            <div
              key={svc.name}
              className="bg-sre-surface border border-sre-border rounded-lg p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-mono text-sre-text-bright">{svc.name}</span>
                <span
                  className={cn(
                    'text-xs font-mono px-2 py-0.5 rounded',
                    svc.status === 'healthy'
                      ? 'bg-sre-success/10 text-sre-success'
                      : svc.status === 'degraded'
                        ? 'bg-sre-error/10 text-sre-error'
                        : 'bg-sre-warning/10 text-sre-warning',
                  )}
                >
                  {svc.status}
                </span>
              </div>
              <div className="grid grid-cols-4 gap-2 text-[11px] font-mono text-sre-text-dim">
                <Metric label="CPU" value={`${svc.cpu_percent}%`} />
                <Metric label="Mem" value={`${svc.memory_percent}%`} />
                <Metric label="Err" value={`${svc.error_rate}%`} />
                <Metric label="p99" value={`${svc.latency_ms}ms`} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Incidents */}
      <div id="incidents">
        <h2 className="text-sm font-medium text-sre-text-dim mb-3 tracking-wide">
          Incident History
        </h2>
        {incidents.length === 0 ? (
          <div className="bg-sre-surface border border-sre-border rounded-lg p-8 text-center">
            <p className="text-sre-text-dim text-sm">
              No incidents recorded. Use the simulation button to trigger a demo.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {incidents.map((inc, idx) => (
              <a
                key={inc.id || `inc-${idx}`}
                href={`/incidents/${inc.id}`}
                className="block bg-sre-surface border border-sre-border rounded-lg p-4 hover:border-sre-border-light transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        'w-2 h-2 rounded-full',
                        inc.status === 'resolved'
                          ? 'bg-sre-success'
                          : inc.status === 'failed'
                            ? 'bg-sre-error'
                            : 'bg-sre-warning status-pulse',
                      )}
                    />
                    <div>
                      <span className="text-sm text-sre-text-bright">{inc.title}</span>
                      <span className="text-xs font-mono text-sre-text-dim ml-3">
                        {inc.service}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-xs font-mono">
                    <span className={severityColor(inc.severity)}>{inc.severity}</span>
                    <span className={statusColor(inc.status)}>{inc.status.replace('_', ' ')}</span>
                    <span className="text-sre-text-dim">
                      {formatTimestamp(inc.created_at)}
                    </span>
                    {inc.duration_seconds && (
                      <span className="text-sre-text-dim">
                        {formatDuration(inc.duration_seconds)}
                      </span>
                    )}
                  </div>
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusCard({
  label,
  value,
  valueClass,
  pulse,
}: {
  label: string;
  value: string;
  valueClass: string;
  pulse?: boolean;
}) {
  return (
    <div className="bg-sre-surface border border-sre-border rounded-lg p-4">
      <div className="text-[11px] font-mono text-sre-text-dim mb-2">{label}</div>
      <div className={cn('text-lg font-semibold font-mono', valueClass, pulse && 'status-pulse')}>
        {value}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-sre-text-dim">{label}</div>
      <div className="text-sre-text">{value}</div>
    </div>
  );
}
