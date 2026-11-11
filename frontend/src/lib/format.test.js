import { describe, expect, it } from 'vitest';
import { accessDetails } from './format.js';

describe('accessDetails', () => {
  it('describes QR and keypad access the way people read it', () => {
    expect(accessDetails({ user: 'sup@example.org', method: 'qr', seconds: 5 })).toBe('QR page, sup@example.org, open 5 s');
    expect(accessDetails({ method: 'keypad', reason: 'wrong PIN', purpose: 'unlock', attempt: 3, lockedOutS: 60 }))
      .toBe('keypad, wrong PIN (3/3), keypad locked 60 s');
    expect(accessDetails({ method: 'keypad', reason: 'wrong PIN', purpose: 'acknowledge', attempt: 1 }))
      .toBe('keypad, wrong PIN (1/3), to acknowledge');
  });
});
