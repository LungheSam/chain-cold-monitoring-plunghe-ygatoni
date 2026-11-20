// Reads settings from environment variables (loaded from backend/.env by `npm run dev`,
// or set as Railway variables in production). See backend/.env.example.

const list = (text) => text.split(',').map((s) => s.trim()).filter(Boolean);

export function loadConfig(env = process.env) {
  const store = env.STORE || 'firestore';
  return {
    port: Number(env.PORT || 3000),
    publicBaseUrl: env.PUBLIC_BASE_URL || 'http://localhost:3000',
    corsOrigins: list(env.CORS_ORIGIN || 'http://localhost:5173'),
    unitIds: list(env.UNIT_IDS || 'cold-unit-01'),
    store, // "firestore" or "memory"
    // DEV_AUTH only works together with the memory store (never against real data)
    devAuth: env.DEV_AUTH === '1' && store === 'memory',
    // Used until the node reports its own thresholds in telemetry (demo profile values)
    defaultThresholds: { minC: 2.0, maxC: 8.0, confirmDelayS: 20, doorLimitS: 15 },
    commandTimeoutMs: Number(env.COMMAND_TIMEOUT_MS || 10000),
    mqtt: {
      url: env.MQTT_URL || 'mqtts://localhost:8883',
      caFile: env.MQTT_CA_FILE || '',
      username: env.MQTT_USERNAME || '',
      password: env.MQTT_PASSWORD || '',
    },
    firebase: {
      projectId: env.FIREBASE_PROJECT_ID || '',
      serviceAccountJson: env.FIREBASE_SERVICE_ACCOUNT || '',
    },
    sms: {
      username: env.AT_USERNAME || 'sandbox',
      apiKey: env.AT_API_KEY || '',
      senderId: env.AT_SENDER_ID || '',
    },
    // Backup channel: every SMS text is also sent to these Telegram chats (empty = off)
    telegram: {
      botToken: env.TELEGRAM_BOT_TOKEN || '',
      chatIds: (env.TELEGRAM_CHAT_IDS || '').split(',').map((s) => s.trim()).filter(Boolean),
    },
  };
}
