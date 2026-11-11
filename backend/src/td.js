// W3C WoT Thing Description 1.1 for one cold unit. Served at GET /things/{unitId}.
// Every form href is relative to `base` and matches a real route in wot.js (checked by a test).
import { EVENT_TYPES, thresholdsSchema, unlockInputSchema } from './schemas.js';

// Property name in the TD -> field name in the live state
export const PROPERTY_FIELDS = {
  internalTemperature: 'internalTemp',
  ambientTemperature: 'ambientTemp',
  humidity: 'humidity',
  doorOpen: 'doorOpen',
  mainsPower: 'mainsPower',
  status: 'status',
  outOfRangeSeconds: 'outOfRangeSeconds',
};

const PUBLIC = ['nosec_sc'];
const SUPERVISOR = ['bearer_sc'];

function readOnly(title, schema) {
  return { title, ...schema, readOnly: true, observable: false };
}

export function buildThingDescription(unitId, publicBaseUrl) {
  const prop = (name) => [{ href: `properties/${name}`, op: ['readproperty'], contentType: 'application/json' }];

  const properties = {
    internalTemperature: readOnly('Internal temperature', { type: 'number', unit: 'degree Celsius', description: 'DS18B20 probe inside the unit. null when the probe has failed.' }),
    ambientTemperature: readOnly('Ambient temperature', { type: 'number', unit: 'degree Celsius', description: 'DHT22 outside the unit.' }),
    humidity: readOnly('Ambient humidity', { type: 'number', unit: 'percent', minimum: 0, maximum: 100 }),
    doorOpen: readOnly('Door open', { type: 'boolean' }),
    mainsPower: readOnly('Mains power present', { type: 'boolean', description: '12 V supply of the cooling unit.' }),
    status: readOnly('Status', { type: 'string', enum: ['OK', 'WARNING', 'ALARM', 'OFFLINE'] }),
    outOfRangeSeconds: readOnly('Cumulative time out of range', { type: 'integer', unit: 'second', minimum: 0, description: 'Total time outside the safe range (2 to 8 C by default).' }),
  };
  for (const name of Object.keys(properties)) properties[name].forms = prop(name);

  properties.thresholds = {
    title: 'Alarm thresholds',
    ...thresholdsSchema,
    readOnly: false,
    writeOnly: false,
    observable: false,
    forms: [
      { href: 'properties/thresholds', op: ['readproperty'], contentType: 'application/json' },
      { href: 'properties/thresholds', op: ['writeproperty'], 'htv:methodName': 'PUT', contentType: 'application/json', security: SUPERVISOR },
    ],
  };

  // (TD data schemas allow one type per field, so "string or null" is written with oneOf)
  const commandResult = {
    type: 'object',
    properties: {
      id: { type: 'string' },
      ok: { type: 'boolean' },
      error: { oneOf: [{ type: 'string' }, { type: 'null' }], description: 'null when ok' },
    },
  };
  const action = (title, description, input) => {
    const a = { title, description, safe: false, idempotent: false, output: commandResult };
    if (input) a.input = input;
    return a;
  };
  const actions = {
    acknowledgeAlarm: action('Acknowledge alarm', 'Silences the buzzer for the current alarms. The red LED stays on until the condition clears.'),
    setThresholds: action('Set thresholds', 'Changes the temperature range, the confirmation delay and the door limit.', { ...thresholdsSchema }),
    unlockDoor: action('Unlock door', 'Opens the solenoid lock for a few seconds (at most 5).', { ...unlockInputSchema }),
  };
  for (const name of Object.keys(actions)) {
    actions[name].forms = [{ href: `actions/${name}`, op: ['invokeaction'], 'htv:methodName': 'POST', contentType: 'application/json', security: SUPERVISOR }];
  }

  const eventData = {
    type: 'object',
    properties: {
      id: { type: 'string' }, ts: { type: 'integer', description: 'Unix time in ms' },
      type: { type: 'string' }, details: { type: 'object' },
    },
  };
  const events = {};
  for (const type of EVENT_TYPES) {
    events[type] = {
      title: type.toLowerCase().replace(/_/g, ' '),
      data: eventData,
      forms: [{ href: `events/${type}`, op: ['subscribeevent'], subprotocol: 'sse', contentType: 'text/event-stream' }],
    };
  }

  return {
    '@context': 'https://www.w3.org/2022/wot/td/v1.1',
    '@type': 'Thing',
    id: `urn:coldchain:${unitId}`,
    title: `Cold unit ${unitId}`,
    description: 'Vaccine storage unit (+2 to +8 C) monitored by a Raspberry Pi edge node. CMU Africa 04-645 IoT project.',
    base: `${publicBaseUrl.replace(/\/$/, '')}/things/${unitId}/`,
    securityDefinitions: {
      nosec_sc: { scheme: 'nosec', description: 'Reads and events are public.' },
      bearer_sc: { scheme: 'bearer', in: 'header', format: 'jwt', alg: 'RS256', description: 'Firebase ID token of a user with the supervisor role.' },
    },
    security: PUBLIC,
    properties,
    actions,
    events,
    forms: [
      { href: 'properties', op: ['readallproperties'], contentType: 'application/json' },
      { href: 'events', op: ['subscribeallevents'], subprotocol: 'sse', contentType: 'text/event-stream' },
    ],
  };
}
