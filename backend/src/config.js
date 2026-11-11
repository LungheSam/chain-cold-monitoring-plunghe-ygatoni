// Reads settings from environment variables (loaded from backend/.env by `npm run dev`).

export function loadConfig(env = process.env) {
  return {
    port: Number(env.PORT || 3000),
    publicBaseUrl: env.PUBLIC_BASE_URL || 'http://localhost:3000',
    corsOrigin: env.CORS_ORIGIN || 'http://localhost:5173',
    unitIds: (env.UNIT_IDS || 'cold-unit-01').split(',').map((s) => s.trim()),
    mqtt: {
      url: env.MQTT_URL || 'mqtts://localhost:8883',
      caFile: env.MQTT_CA_FILE || '',
      username: env.MQTT_USERNAME || '',
      password: env.MQTT_PASSWORD || '',
    },
    sms: {
      username: env.AT_USERNAME || 'sandbox',
      apiKey: env.AT_API_KEY || '',
      senderId: env.AT_SENDER_ID || '',
    },
  };
}
