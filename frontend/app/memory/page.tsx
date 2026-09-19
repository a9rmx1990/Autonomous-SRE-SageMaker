'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Search, Clock, AlertTriangle, CheckCircle, Database, Tag, ChevronDown, ChevronRight, Zap, BookOpen } from 'lucide-react';
import { cn, formatTimestamp } from '@/lib/utils';

interface IncidentPostmortemContent {
  incident_id?: string;
  service?: string;
  summary?: string;
  root_cause?: string;
  remediation?: string;
  verification_result?: string;
  verification?: string;
  metrics?: Record<string, any>;
  lessons_learned?: string;
  timestamp?: string;
  [key: string]: any;
}

interface MemoryEntry {
  id: string;
  incident_id?: string;
  type?: 'incident' | 'preference' | 'pattern' | string;
  category?: string;
  content: string | IncidentPostmortemContent;
  namespace?: string;
  created_at?: string;
  timestamp?: string;
  tags?: string[];
  metadata?: Record<string, string>;
}

interface IncidentMemory {
  incident_id: string;
  service: string;
  severity?: string;
  summary?: string;
  root_cause: string;
  remediation: string;
  verification?: string;
  verification_result?: string;
  metrics?: Record<string, any>;
  lessons_learned: string;
  timestamp: string;
}

const MOCK_MEMORIES_BASE: Omit<MemoryEntry, 'created_at'>[] = [
  {
    id: 'mem-001',
    type: 'incident',
    namespace: 'incidents',
    content: 'Payment API CPU spike caused by traffic surge exceeding ECS capacity. Remediated by scaling from 2 to 4 tasks. Recovery confirmed within 45 seconds.',
    metadata: { service: 'payment-api', severity: 'high', outcome: 'resolved' },
  },
  {
    id: 'mem-002',
    type: 'pattern',
    namespace: 'patterns',
    content: 'Recurring pattern: payment-api experiences CPU spikes during peak traffic windows (14:00-16:00 UTC). Pre-emptive scaling recommended.',
    metadata: { service: 'payment-api', confidence: '0.87' },
  },
  {
    id: 'mem-003',
    type: 'preference',
    namespace: 'preferences',
    content: 'For payment-api incidents, prefer scale_up over restart_service when CPU > 90% and error rate < 10%. Restart only when containers enter crash loop.',
    metadata: { scope: 'remediation_strategy' },
  },
  {
    id: 'mem-004',
    type: 'incident',
    namespace: 'incidents',
    content: 'Auth service memory leak detected via gradual memory climb over 6 hours. Container restart resolved. Root cause traced to unclosed DB connection pool.',
    metadata: { service: 'auth-service', severity: 'medium', outcome: 'resolved' },
  },
  {
    id: 'mem-005',
    type: 'pattern',
    namespace: 'patterns',
    content: 'Cache flush is effective for latency spikes when p99 > 500ms and cache hit ratio drops below 60%. Otherwise investigate upstream dependencies first.',
    metadata: { confidence: '0.92' },
  },
];

const MOCK_POSTMORTEMS_BASE: Omit<IncidentMemory, 'timestamp'>[] = [
  {
    incident_id: 'inc-sim-001',
    service: 'payment-api',
    severity: 'high',
    root_cause: 'Traffic surge caused CPU utilization to exceed 95%, triggering ECS container crash loops due to insufficient task count.',
    remediation: 'Scaled ECS service from 2 to 4 tasks. CPU dropped to 42% within 30 seconds of new tasks becoming healthy.',
    verification: 'All health checks passed: CPU 42%, Memory 58%, 5xx rate 0.3%, zero container restarts, CloudWatch alarm returned to OK.',
    lessons_learned: 'Pre-scale payment-api before known traffic peaks. Consider setting up predictive auto-scaling based on historical traffic patterns. Current desired count of 2 is insufficient for peak load.',
  },
];

const INITIAL_MEMORIES: MemoryEntry[] = MOCK_MEMORIES_BASE.map((m) => ({ ...m, created_at: '' }));
const INITIAL_POSTMORTEMS: IncidentMemory[] = MOCK_POSTMORTEMS_BASE.map((p) => ({ ...p, timestamp: '' }));

type TabKey = 'postmortems' | 'entries' | 'patterns';

export default function MemoryPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('postmortems');
  const [memories, setMemories] = useState<MemoryEntry[]>(INITIAL_MEMORIES);
  const [postmortems, setPostmortems] = useState<IncidentMemory[]>(INITIAL_POSTMORTEMS);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedPostmortem, setExpandedPostmortem] = useState<string | null>(INITIAL_POSTMORTEMS[0]?.incident_id || null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initialize timestamps on client mount to match server and initial client HTML
    const now = Date.now();
    const offsets = [3600000, 7200000, 86400000, 172800000, 259200000];
    const clientMemories: MemoryEntry[] = MOCK_MEMORIES_BASE.map((m, idx) => ({
      ...m,
      created_at: new Date(now - (offsets[idx] || 3600000)).toISOString(),
    }));
    const clientPostmortems: IncidentMemory[] = MOCK_POSTMORTEMS_BASE.map((p) => ({
      ...p,
      timestamp: new Date(now - 3600000).toISOString(),
    }));

    setMemories(clientMemories);
    setPostmortems(clientPostmortems);

    const fetchMemory = async () => {
      try {
        const res = await fetch('/api/memory');
        if (res.ok) {
          const data = await res.json();
          if (data.entries?.length) {
            setMemories(data.entries);

            // Populate postmortems from entries if category is incident_postmortem
            const extractedPostmortems: IncidentMemory[] = data.entries
              .filter(
                (e: any) =>
                  e.category === 'incident_postmortem' ||
                  (typeof e.content === 'object' && e.content !== null && e.content.incident_id)
              )
              .map((e: any) => {
                const c = typeof e.content === 'object' && e.content !== null ? e.content : {};
                return {
                  incident_id: c.incident_id || e.incident_id || e.id,
                  service: c.service || (Array.isArray(e.tags) ? e.tags[0] : 'payment-api'),
                  severity: c.severity || 'high',
                  summary: c.summary || '',
                  root_cause: c.root_cause || '',
                  remediation: c.remediation || '',
                  verification: c.verification || c.verification_result || '',
                  verification_result: c.verification_result || c.verification || '',
                  metrics: c.metrics || {},
                  lessons_learned: c.lessons_learned || '',
                  timestamp: c.timestamp || e.timestamp || e.created_at || '',
                };
              });

            if (extractedPostmortems.length > 0) {
              setPostmortems(extractedPostmortems);
              setExpandedPostmortem(extractedPostmortems[0]?.incident_id || null);
            }
          }
          if (data.postmortems?.length) {
            setPostmortems(data.postmortems);
            setExpandedPostmortem(data.postmortems[0]?.incident_id || null);
          }
        }
      } catch {
        // Use mock data
      } finally {
        setLoading(false);
      }
    };
    fetchMemory();
  }, []);

  const tabs: { key: TabKey; label: string; icon: React.ReactNode; count: number }[] = [
    { key: 'postmortems', label: 'Post-Mortems', icon: <BookOpen className="w-4 h-4" />, count: postmortems.length },
    {
      key: 'entries',
      label: 'All Entries',
      icon: <Database className="w-4 h-4" />,
      count: memories.filter((m) => m.type === 'incident' || m.category === 'incident_postmortem').length,
    },
    {
      key: 'patterns',
      label: 'Patterns & Preferences',
      icon: <Zap className="w-4 h-4" />,
      count: memories.filter((m) => !(m.type === 'incident' || m.category === 'incident_postmortem')).length,
    },
  ];

  const getContentSearchText = (content: string | IncidentPostmortemContent | Record<string, any>): string => {
    if (typeof content === 'string') return content;
    if (typeof content === 'object' && content !== null) {
      return [
        content.summary,
        content.service,
        content.root_cause,
        content.remediation,
        content.verification_result,
        content.verification,
        content.lessons_learned,
        content.metrics ? JSON.stringify(content.metrics) : '',
      ]
        .filter(Boolean)
        .join(' ');
    }
    return '';
  };

  const filteredMemories = memories.filter((m) => {
    const text = getContentSearchText(m.content);
    const matchesSearch = !searchQuery || text.toLowerCase().includes(searchQuery.toLowerCase());
    const isIncident = m.type === 'incident' || m.category === 'incident_postmortem';
    if (activeTab === 'entries') return isIncident && matchesSearch;
    if (activeTab === 'patterns') return !isIncident && matchesSearch;
    return matchesSearch;
  });

  const typeIcon = (type?: string, category?: string) => {
    const t = type || (category === 'incident_postmortem' ? 'incident' : category);
    switch (t) {
      case 'incident':
      case 'incident_postmortem':
        return <AlertTriangle className="w-4 h-4 text-sre-warning" />;
      case 'pattern':
        return <Zap className="w-4 h-4 text-sre-accent" />;
      case 'preference':
        return <Tag className="w-4 h-4 text-emerald-400" />;
      default:
        return <Database className="w-4 h-4 text-sre-muted" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-sre-text flex items-center gap-3">
            <Brain className="w-7 h-7 text-sre-accent" />
            AgentCore Memory
          </h1>
          <p className="text-sre-muted mt-1 text-sm">
            Incident history, learned patterns, and remediation preferences stored across agent sessions.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-sre-surface border border-sre-border rounded text-xs text-sre-muted">
          <Database className="w-3.5 h-3.5" />
          <span>{memories.length} entries</span>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-sre-muted" />
        <input
          type="text"
          placeholder="Search memory entries..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 bg-sre-surface border border-sre-border rounded text-sm text-sre-text placeholder:text-sre-muted/50 focus:outline-none focus:border-sre-accent/50"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-sre-border">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.key
                ? 'border-sre-accent text-sre-accent'
                : 'border-transparent text-sre-muted hover:text-sre-text'
            )}
          >
            {tab.icon}
            {tab.label}
            <span
              className={cn(
                'text-xs px-1.5 py-0.5 rounded',
                activeTab === tab.key ? 'bg-sre-accent/20 text-sre-accent' : 'bg-sre-surface text-sre-muted'
              )}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Content */}
      <AnimatePresence mode="wait">
        {activeTab === 'postmortems' && (
          <motion.div
            key="postmortems"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="space-y-4"
          >
            {postmortems.length === 0 ? (
              <EmptyState message="No post-mortems stored yet. Run an incident to generate one." />
            ) : (
              postmortems.map((pm, idx) => {
                const isExpanded = expandedPostmortem === pm.incident_id;
                const pmKey = pm.incident_id || `pm-${idx}`;
                const displaySeverity = pm.severity ? pm.severity.toUpperCase() : 'RESOLVED';
                return (
                  <div key={pmKey} className="bg-sre-surface border border-sre-border rounded overflow-hidden">
                    <button
                      onClick={() => setExpandedPostmortem(isExpanded ? null : pm.incident_id)}
                      className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-sre-raised/50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <BookOpen className="w-5 h-5 text-sre-accent" />
                        <div>
                          <div className="text-sm font-medium text-sre-text">
                            {pm.service} — {displaySeverity} Incident
                          </div>
                          <div className="text-xs text-sre-muted mt-0.5">{formatTimestamp(pm.timestamp)}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          Resolved
                        </span>
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-sre-muted" />
                        ) : (
                          <ChevronRight className="w-4 h-4 text-sre-muted" />
                        )}
                      </div>
                    </button>

                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className="px-5 pb-5 space-y-4 border-t border-sre-border pt-4">
                            {pm.summary && (
                              <PostmortemSection
                                title="Summary"
                                icon={<BookOpen className="w-4 h-4 text-sre-accent" />}
                                content={pm.summary}
                              />
                            )}
                            <PostmortemSection
                              title="Root Cause"
                              icon={<AlertTriangle className="w-4 h-4 text-sre-error" />}
                              content={pm.root_cause}
                            />
                            <PostmortemSection
                              title="Remediation Applied"
                              icon={<Zap className="w-4 h-4 text-sre-warning" />}
                              content={pm.remediation}
                            />
                            <PostmortemSection
                              title="Verification"
                              icon={<CheckCircle className="w-4 h-4 text-emerald-400" />}
                              content={pm.verification || pm.verification_result || ''}
                            />
                            {pm.metrics && Object.keys(pm.metrics).length > 0 && (
                              <PostmortemSection
                                title="Metrics"
                                icon={<Database className="w-4 h-4 text-sre-info" />}
                                content={typeof pm.metrics === 'object' ? JSON.stringify(pm.metrics, null, 2) : String(pm.metrics)}
                                isCode
                              />
                            )}
                            <PostmortemSection
                              title="Lessons Learned"
                              icon={<Brain className="w-4 h-4 text-sre-accent" />}
                              content={pm.lessons_learned}
                              highlight
                            />
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })
            )}
          </motion.div>
        )}

        {(activeTab === 'entries' || activeTab === 'patterns') && (
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="space-y-3"
          >
            {filteredMemories.length === 0 ? (
              <EmptyState message={searchQuery ? 'No entries match your search.' : 'No memory entries yet.'} />
            ) : (
              filteredMemories.map((entry, idx) => {
                const isObject = typeof entry.content === 'object' && entry.content !== null;
                const contentObj = isObject ? (entry.content as IncidentPostmortemContent) : null;
                const displayType =
                  entry.type || (entry.category === 'incident_postmortem' ? 'incident' : entry.category || 'entry');
                const displayNamespace =
                  entry.namespace ||
                  (Array.isArray(entry.tags) ? entry.tags.join(', ') : entry.incident_id || '');
                const displayTime =
                  entry.created_at || entry.timestamp || (contentObj ? contentObj.timestamp : '') || '';

                return (
                  <div
                    key={entry.id || `mem-${idx}`}
                    className="bg-sre-surface border border-sre-border rounded px-5 py-4"
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5">{typeIcon(entry.type, entry.category)}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-sre-raised text-sre-muted uppercase">
                            {displayType}
                          </span>
                          {displayNamespace && (
                            <span className="text-xs text-sre-muted/60 font-mono">{displayNamespace}</span>
                          )}
                          <span className="text-xs text-sre-muted/40 ml-auto flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatTimestamp(displayTime)}
                          </span>
                        </div>

                        {contentObj ? (
                          <div className="space-y-3">
                            {contentObj.summary && (
                              <div className="text-sm font-semibold text-sre-text">
                                {contentObj.summary}
                              </div>
                            )}
                            {contentObj.service && (
                              <div className="flex items-center gap-2 text-xs">
                                <span className="text-sre-muted font-mono uppercase text-[10px]">Service:</span>
                                <span className="text-sre-text font-mono bg-sre-raised px-1.5 py-0.5 rounded border border-sre-border/50">
                                  {contentObj.service}
                                </span>
                              </div>
                            )}
                            {contentObj.root_cause && (
                              <div className="text-xs">
                                <span className="text-sre-error font-mono uppercase text-[10px] block mb-1 font-semibold">
                                  Root Cause:
                                </span>
                                <p className="text-sre-text/90 leading-relaxed bg-sre-bg p-2.5 rounded border border-sre-border/40">
                                  {contentObj.root_cause}
                                </p>
                              </div>
                            )}
                            {contentObj.remediation && (
                              <div className="text-xs">
                                <span className="text-sre-warning font-mono uppercase text-[10px] block mb-1 font-semibold">
                                  Remediation:
                                </span>
                                <p className="text-sre-text/90 leading-relaxed bg-sre-bg p-2.5 rounded border border-sre-border/40">
                                  {contentObj.remediation}
                                </p>
                              </div>
                            )}
                            {(contentObj.verification_result || contentObj.verification) && (
                              <div className="text-xs">
                                <span className="text-emerald-400 font-mono uppercase text-[10px] block mb-1 font-semibold">
                                  Verification Result:
                                </span>
                                <p className="text-emerald-400/90 leading-relaxed bg-sre-bg p-2.5 rounded border border-sre-border/40">
                                  {contentObj.verification_result || contentObj.verification}
                                </p>
                              </div>
                            )}
                            {contentObj.metrics && (
                              <div className="text-xs">
                                <span className="text-sre-muted font-mono uppercase text-[10px] block mb-1 font-semibold">
                                  Metrics:
                                </span>
                                <pre className="p-2.5 rounded bg-sre-raised text-[11px] font-mono text-sre-text-dim overflow-x-auto border border-sre-border/50">
                                  {typeof contentObj.metrics === 'object'
                                    ? JSON.stringify(contentObj.metrics, null, 2)
                                    : String(contentObj.metrics)}
                                </pre>
                              </div>
                            )}
                            {contentObj.lessons_learned && (
                              <div className="text-xs p-3 rounded bg-sre-accent/5 border border-sre-accent/20">
                                <span className="text-sre-accent font-mono uppercase text-[10px] block mb-1 font-semibold">
                                  Lessons Learned:
                                </span>
                                <p className="text-sre-text/90 leading-relaxed">
                                  {contentObj.lessons_learned}
                                </p>
                              </div>
                            )}
                            {Object.entries(contentObj)
                              .filter(
                                ([k]) =>
                                  ![
                                    'incident_id',
                                    'service',
                                    'summary',
                                    'root_cause',
                                    'remediation',
                                    'verification_result',
                                    'verification',
                                    'metrics',
                                    'lessons_learned',
                                    'timestamp',
                                  ].includes(k)
                              )
                              .map(([k, v]) => (
                                <div key={k} className="text-xs">
                                  <span className="text-sre-muted font-mono uppercase text-[10px] block mb-1">{k}:</span>
                                  {typeof v === 'object' && v !== null ? (
                                    <pre className="p-2 rounded bg-sre-raised text-[11px] font-mono text-sre-text-dim overflow-x-auto">
                                      {JSON.stringify(v, null, 2)}
                                    </pre>
                                  ) : (
                                    <p className="text-sre-text/90 leading-relaxed">{String(v ?? '')}</p>
                                  )}
                                </div>
                              ))}
                          </div>
                        ) : (
                          <p className="text-sm text-sre-text/90 leading-relaxed">
                            {String(entry.content ?? '')}
                          </p>
                        )}

                        {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                          <div className="flex flex-wrap gap-2 mt-3">
                            {Object.entries(entry.metadata).map(([k, v]) => (
                              <span
                                key={k}
                                className="text-xs font-mono px-2 py-0.5 rounded bg-sre-bg border border-sre-border text-sre-muted"
                              >
                                {k}: {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* How Memory Works */}
      <div className="mt-8 bg-sre-surface border border-sre-border rounded p-5">
        <h3 className="text-sm font-semibold text-sre-text mb-3 flex items-center gap-2">
          <Brain className="w-4 h-4 text-sre-accent" />
          How AgentCore Memory Works
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              step: '1',
              title: 'Before Investigation',
              desc: 'The orchestrator retrieves relevant past incidents and preferences to inform the current investigation.',
            },
            {
              step: '2',
              title: 'During Resolution',
              desc: 'Agents reference stored remediation strategies and known failure patterns to make faster decisions.',
            },
            {
              step: '3',
              title: 'After Resolution',
              desc: 'The full incident post-mortem, root cause, and lessons learned are stored for future reference.',
            },
          ].map((item) => (
            <div key={item.step} className="flex gap-3">
              <div className="flex-shrink-0 w-7 h-7 rounded bg-sre-accent/10 border border-sre-accent/20 flex items-center justify-center text-xs font-bold text-sre-accent">
                {item.step}
              </div>
              <div>
                <div className="text-sm font-medium text-sre-text">{item.title}</div>
                <div className="text-xs text-sre-muted mt-0.5 leading-relaxed">{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PostmortemSection({
  title,
  icon,
  content,
  highlight,
  isCode,
}: {
  title: string;
  icon: React.ReactNode;
  content: string | Record<string, unknown> | unknown;
  highlight?: boolean;
  isCode?: boolean;
}) {
  const isObject = typeof content === 'object' && content !== null;
  const displayContent = isObject ? JSON.stringify(content, null, 2) : String(content ?? '');

  return (
    <div className={cn('rounded p-3', highlight ? 'bg-sre-accent/5 border border-sre-accent/20' : 'bg-sre-bg')}>
      <div className="flex items-center gap-2 mb-1.5">
        {icon}
        <span className="text-xs font-semibold text-sre-text uppercase tracking-wide">{title}</span>
      </div>
      {isCode || isObject ? (
        <pre className="text-xs font-mono text-sre-text/80 leading-relaxed overflow-x-auto bg-sre-surface/50 p-2.5 rounded border border-sre-border/50">
          {displayContent}
        </pre>
      ) : (
        <p className="text-sm text-sre-text/80 leading-relaxed">{displayContent}</p>
      )}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-sre-muted">
      <Database className="w-10 h-10 mb-3 opacity-30" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
