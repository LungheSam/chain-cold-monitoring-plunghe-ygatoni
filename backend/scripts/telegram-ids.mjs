// Prints the chat ids of the people (or groups) who have sent a message to your Telegram bot.
// 1. Put TELEGRAM_BOT_TOKEN=... in backend/.env (from @BotFather).
// 2. In Telegram, open your bot and send it any message (for example "hi").
// 3. Run:  npm run telegram-ids
// Copy the ids into TELEGRAM_CHAT_IDS (comma separated) on Railway.
const token = process.env.TELEGRAM_BOT_TOKEN;
if (!token) {
  console.error('TELEGRAM_BOT_TOKEN is not set (add it to backend/.env)');
  process.exit(1);
}
const res = await fetch(`https://api.telegram.org/bot${token}/getUpdates`);
const data = await res.json();
if (!data.ok) {
  console.error(`Telegram said: ${data.description || res.status}`);
  process.exit(1);
}
const chats = new Map();
for (const u of data.result) {
  const chat = (u.message || u.channel_post || u.my_chat_member || {}).chat;
  if (chat) chats.set(chat.id, chat.title || [chat.first_name, chat.last_name].filter(Boolean).join(' ') || chat.username);
}
if (chats.size === 0) {
  console.log('No messages yet: send your bot a message in Telegram, then run this again.');
} else {
  for (const [id, name] of chats) console.log(`${id}  ${name}`);
  console.log(`\nTELEGRAM_CHAT_IDS=${[...chats.keys()].join(',')}`);
}
