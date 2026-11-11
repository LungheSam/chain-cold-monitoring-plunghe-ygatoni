// JSON schemas (checked with ajv) for everything that comes from outside: MQTT messages from the
// node and HTTP request bodies. Anything that does not match is rejected before it is used.
import Ajv from 'ajv';

export const EVENT_TYPES = [
  'OUT_OF_RANGE_HIGH', 'OUT_OF_RANGE_LOW', 'BACK_IN_RANGE', 'DOOR_OPEN_TOO_LONG', 'DOOR_CLOSED',
  'POWER_LOST', 'POWER_RESTORED', 'SENSOR_FAULT', 'SENSOR_RESTORED', 'ALARM_ACKNOWLEDGED',
  'ACCESS_GRANTED', 'ACCESS_DENIED',
];

const nullableNumber = { type: ['number', 'null'] };

export const thresholdsSchema = {
  type: 'object',
  properties: {
    minC: { type: 'number', minimum: -30, maximum: 30 },
    maxC: { type: 'number', minimum: -30, maximum: 30 },
    confirmDelayS: { type: 'integer', minimum: 0, maximum: 3600 },
    doorLimitS: { type: 'integer', minimum: 1, maximum: 3600 },
  },
  additionalProperties: false,
};

const telemetrySchema = {
  type: 'object',
  required: ['ts', 'status', 'internalTemp', 'doorOpen', 'mainsPower', 'outOfRangeSeconds'],
  properties: {
    ts: { type: 'integer' },
    internalTemp: nullableNumber,
    ambientTemp: nullableNumber,
    humidity: nullableNumber,
    doorOpen: { type: 'boolean' },
    mainsPower: { type: 'boolean' },
    status: { enum: ['OK', 'WARNING', 'ALARM'] },
    outOfRangeSeconds: { type: 'number', minimum: 0 },
    timeSynced: { type: 'boolean' },
    thresholds: thresholdsSchema,
  },
};

const eventSchema = {
  type: 'object',
  required: ['id', 'ts', 'type', 'details'],
  properties: {
    id: { type: 'string', minLength: 1, maxLength: 64 },
    ts: { type: 'integer' },
    type: { enum: EVENT_TYPES },
    details: { type: 'object' },
    timeSynced: { type: 'boolean' },
  },
};

const cmdResultSchema = {
  type: 'object',
  required: ['id', 'ok'],
  properties: {
    id: { type: ['string', 'null'] },
    ok: { type: 'boolean' },
    error: { type: ['string', 'null'] },
  },
};

export const unlockInputSchema = {
  type: 'object',
  properties: { seconds: { type: 'integer', minimum: 1, maximum: 5 } },
  additionalProperties: false,
};

const contactSchema = {
  type: 'object',
  required: ['name', 'phone'],
  properties: {
    name: { type: 'string', minLength: 1, maxLength: 60 },
    // International format, e.g. +250788123456 (Rwanda mobile numbers are +2507 and 8 digits)
    phone: { type: 'string', pattern: '^\\+[1-9][0-9]{7,14}$' },
    units: { type: 'array', items: { type: 'string', maxLength: 64 }, maxItems: 50 },
    active: { type: 'boolean' },
  },
  additionalProperties: false,
};

const ajv = new Ajv({ allErrors: true });
export const validateTelemetry = ajv.compile(telemetrySchema);
export const validateEvent = ajv.compile(eventSchema);
export const validateCmdResult = ajv.compile(cmdResultSchema);
export const validateThresholds = ajv.compile({ ...thresholdsSchema, minProperties: 1 });
export const validateUnlockInput = ajv.compile(unlockInputSchema);
export const validateContact = ajv.compile(contactSchema);

// Short text for an HTTP 400 answer
export function errorText(validate) {
  return ajv.errorsText(validate.errors, { dataVar: 'body' });
}
