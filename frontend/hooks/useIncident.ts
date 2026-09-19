'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { Incident, IncidentEvent } from '@/lib/api';
import { getIncident, subscribeToEvents } from '@/lib/api';

export function useIncident(id: string) {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [events, setEvents] = useState<IncidentEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getIncident(id);
      setIncident(data);
      setEvents(data.events || []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load incident');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    refresh();

    // Subscribe to SSE
    const es = subscribeToEvents(
      id,
      (event) => {
        if (event.message === 'keepalive') return;
        setEvents((prev) => {
          // Deduplicate by ID
          if (prev.some((e) => e.id === event.id)) return prev;
          return [...prev, event];
        });
        // Refresh full incident periodically
        refresh();
      },
      () => {
        // On error, try to reconnect after delay
        setTimeout(() => refresh(), 3000);
      },
    );
    esRef.current = es;

    return () => {
      es.close();
    };
  }, [id, refresh]);

  return { incident, events, loading, error, refresh };
}
