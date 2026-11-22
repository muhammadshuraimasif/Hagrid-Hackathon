import { describe, it, expect, beforeEach, vi } from 'vitest';
import 'fake-indexeddb/auto';
import { db, queueOutboxEvent, syncOutboxEvents } from '../db/outbox';
import { api } from '../api/client';

describe('Dexie Offline Outbox & Sync Queue', () => {
  beforeEach(async () => {
    await db.events.clear();
    vi.restoreAllMocks();
  });

  it('stores the same client UUID twice exactly once (idempotent)', async () => {
    const testUuid = 'client-uuid-12345';
    const caseId = 'case-test-01';

    // Queue event first time
    await queueOutboxEvent(testUuid, caseId, 'CONSENT_GRANTED', { scope: 'all' });
    let count = await db.events.count();
    expect(count).toBe(1);

    // Queue identical UUID a second time with updated payload
    await queueOutboxEvent(testUuid, caseId, 'CONSENT_GRANTED', { scope: 'all', replayed: true });
    count = await db.events.count();
    expect(count).toBe(1); // Still exactly one entry

    const saved = await db.events.get(testUuid);
    expect(saved).toBeDefined();
    expect(saved?.id).toBe(testUuid);
    expect(saved?.payload?.replayed).toBe(true);
  });

  it('replays unsynced events after being offline and marks them synced', async () => {
    // Mock the backend /sync/push API call
    const mockPost = vi.spyOn(api, 'post').mockResolvedValue({
      received: 2,
      processed: 2,
      conflicts: 0,
    });

    // Queue two offline events
    await queueOutboxEvent('uuid-event-1', 'case-01', 'CASE_SUBMITTED', { amount: 25000 });
    await queueOutboxEvent('uuid-event-2', 'case-01', 'DOCUMENTS_ATTACHED', { count: 2 });

    const unsyncedBefore = await db.events.where('synced').equals(0).count();
    expect(unsyncedBefore).toBe(2);

    // Replay / sync outbox
    const result = await syncOutboxEvents();
    expect(result.pushed).toBe(2);
    expect(result.failed).toBe(0);

    // Confirm backend was called with both events
    expect(mockPost).toHaveBeenCalledWith('/sync/push', {
      events: expect.arrayContaining([
        expect.objectContaining({ client_uuid: 'uuid-event-1' }),
        expect.objectContaining({ client_uuid: 'uuid-event-2' }),
      ]),
    });

    // Confirm locally marked as synced
    const unsyncedAfter = await db.events.where('synced').equals(0).count();
    expect(unsyncedAfter).toBe(0);
  });
});
