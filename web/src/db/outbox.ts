/**
 * Dexie Offline Database & Outbox Queue for Project Amaanat.
 * 
 * Guarantees offline-first resilience:
 * - Every citizen action is assigned a client-generated UUID.
 * - Outbox stores events locally; idempotent replay on server sync.
 * - Same UUID pushed twice is stored once.
 */
import Dexie, { type EntityTable } from 'dexie';
import { api } from '../api/client';

export interface OutboxEvent {
  id: string; // client_uuid
  case_id: string;
  event_type: string;
  payload: Record<string, any>;
  created_at: string;
  synced: number; // 0 = unsynced, 1 = synced
}

export interface OfflineDraft {
  case_id: string;
  step: number;
  data: Record<string, any>;
  updated_at: string;
}

export class AmaanatDatabase extends Dexie {
  events!: EntityTable<OutboxEvent, 'id'>;
  drafts!: EntityTable<OfflineDraft, 'case_id'>;

  constructor() {
    super('AmaanatOfflineDB');
    this.version(1).stores({
      events: 'id, case_id, event_type, synced, created_at',
      drafts: 'case_id, step, updated_at',
    });
  }
}

export const db = new AmaanatDatabase();

/**
 * Queues an action into the local Dexie outbox.
 * Idempotent: putting the same UUID twice updates or preserves the entry without duplicating.
 */
export async function queueOutboxEvent(
  id: string,
  caseId: string,
  eventType: string,
  payload: Record<string, any>
): Promise<OutboxEvent> {
  const event: OutboxEvent = {
    id,
    case_id: caseId,
    event_type: eventType,
    payload,
    created_at: new Date().toISOString(),
    synced: 0,
  };
  await db.events.put(event);
  return event;
}

/**
 * Pushes unsynced local events to the backend /sync/push endpoint.
 */
export async function syncOutboxEvents(): Promise<{ pushed: number; failed: number }> {
  const unsynced = await db.events.where('synced').equals(0).toArray();
  if (unsynced.length === 0) {
    return { pushed: 0, failed: 0 };
  }

  try {
    const payloadEvents = unsynced.map((e) => ({
      client_uuid: e.id,
      case_id: e.case_id,
      event_type: e.event_type,
      payload: e.payload,
      created_at: e.created_at,
    }));

    await api.post('/sync/push', { events: payloadEvents });

    // Mark as synced locally
    await db.transaction('rw', db.events, async () => {
      for (const e of unsynced) {
        await db.events.update(e.id, { synced: 1 });
      }
    });

    return { pushed: unsynced.length, failed: 0 };
  } catch (err) {
    return { pushed: 0, failed: unsynced.length };
  }
}
