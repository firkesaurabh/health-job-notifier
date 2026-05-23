// ── worker.js ─────────────────────────────────────────────────────────────────
// Cloudflare Worker — instant Telegram webhook handler
// Environment variables needed (set in CF dashboard):
//   TELEGRAM_TOKEN   — bot token
//   TELEGRAM_CHAT_ID — your chat ID
//   GH_TOKEN         — GitHub PAT with repo + workflow scope

const REPO   = "firkesaurabh/health-job-notifier";
const BRANCH = "main";

const MENU_KB = {
  inline_keyboard: [
    [
      { text: "🔍 Scan Now", callback_data: "scan"   },
      { text: "📊 Status",   callback_data: "status" },
    ],
    [
      { text: "📈 Stats",    callback_data: "stats"  },
      { text: "❓ Help",     callback_data: "help"   },
    ],
  ],
};

// ── Telegram API ──────────────────────────────────────────────────────────────
async function tg(method, payload, token) {
  const r = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return r.json();
}

async function send(chatId, text, token, extra = {}) {
  return tg("sendMessage", {
    chat_id: chatId,
    text,
    parse_mode: "HTML",
    disable_web_page_preview: true,
    reply_markup: MENU_KB,
    ...extra,
  }, token);
}

async function answerCb(cbId, token, text = "") {
  return tg("answerCallbackQuery", { callback_query_id: cbId, text }, token);
}

// ── GitHub helpers ────────────────────────────────────────────────────────────
async function triggerScan(ghToken) {
  const r = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/scan.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `token ${ghToken}`,
        Accept: "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "cf-job-bot",
      },
      body: JSON.stringify({ ref: BRANCH }),
    }
  );
  return r.status === 204;
}

async function fetchScanLog(ghToken) {
  try {
    const r = await fetch(
      `https://api.github.com/repos/${REPO}/contents/scan_log.json`,
      {
        headers: {
          Authorization: `token ${ghToken}`,
          Accept: "application/vnd.github.v3+json",
          "User-Agent": "cf-job-bot",
        },
      }
    );
    const data = await r.json();
    if (data.content) {
      return JSON.parse(atob(data.content.replace(/\n/g, "")));
    }
  } catch (e) {}
  return null;
}

// ── Action handlers ───────────────────────────────────────────────────────────
async function handleScan(chatId, token, ghToken) {
  const ok = await triggerScan(ghToken);
  await send(chatId,
    ok
      ? "🔍 <b>Scan triggered!</b>\nGitHub spinning up... results arrive as Telegram alert in ~2 min."
      : "⚠️ Failed to trigger scan. Check GitHub Actions.",
    token
  );
}

async function handleStatus(chatId, token, ghToken) {
  const log = await fetchScanLog(ghToken);

  if (!log || !log.last_run) {
    return send(chatId, "No scan data yet. Tap 🔍 Scan Now to run one.", token);
  }

  const now      = new Date();
  const nextRun  = new Date(now);
  nextRun.setMinutes(0, 0, 0);
  nextRun.setHours(nextRun.getHours() + 1);
  const minsLeft = Math.round((nextRun - now) / 60000);

  let text =
    `📊 <b>Scanner Status</b>\n\n` +
    `🕐 Last run:      ${log.last_run} UTC\n` +
    `📋 Jobs found:    ${log.jobs_collected ?? 0}\n` +
    `🆕 New (unseen):  ${log.new_jobs ?? 0}\n` +
    `✅ Matches:       ${log.matches ?? 0}\n` +
    `📈 All-time:      ${log.total_matches ?? 0} matches / ${log.total_runs ?? 0} runs`;

  if (log.last_matches && log.last_matches.length > 0) {
    text += "\n\n<b>Last matches:</b>";
    log.last_matches.slice(0, 3).forEach(m => {
      text += `\n  • ${m.title} @ ${m.company}`;
    });
  }

  text += `\n\n⏰ Next auto-scan in ~${minsLeft} min`;
  await send(chatId, text, token);
}

async function handleStats(chatId, token, ghToken) {
  const log = await fetchScanLog(ghToken);
  await send(chatId,
    `📈 <b>All-time Stats</b>\n\n` +
    `Total scans:   ${log?.total_runs ?? 0}\n` +
    `Total matches: ${log?.total_matches ?? 0}\n` +
    `Last scan:     ${log?.last_run ?? "never"} UTC`,
    token
  );
}

async function handleHelp(chatId, token) {
  await send(chatId,
    `🤖 <b>Health Job Bot</b>\n\n` +
    `Say <b>hi</b> for this menu, or use:\n` +
    `/scan   — trigger scan now\n` +
    `/status — last run info\n` +
    `/stats  — all-time totals\n` +
    `/help   — this message\n\n` +
    `Auto-scans every hour. Instant alert for new BA jobs at TPA / Insurer / HealthTech.`,
    token
  );
}

// ── Main update handler ───────────────────────────────────────────────────────
async function handleUpdate(update, env) {
  const token  = env.TELEGRAM_TOKEN;
  const chatId = env.TELEGRAM_CHAT_ID;
  const ghToken = env.GH_TOKEN;

  // ── Inline button press ───────────────────────────────────────────────────
  const cb = update.callback_query;
  if (cb) {
    await answerCb(cb.id, token);
    const action = cb.data;
    if      (action === "scan")   await handleScan(chatId, token, ghToken);
    else if (action === "status") await handleStatus(chatId, token, ghToken);
    else if (action === "stats")  await handleStats(chatId, token, ghToken);
    else if (action === "help")   await handleHelp(chatId, token);
    return;
  }

  // ── Text message ─────────────────────────────────────────────────────────
  const msg = update.message;
  if (!msg || !msg.text) return;

  const text = msg.text.toLowerCase().split("@")[0].trim();

  if (["hi", "hello", "hey", "/start"].includes(text)) {
    await send(chatId, "👋 <b>Hey Saurabh!</b> What do you want to do?", token);
  } else if (["/scan", "scan"].includes(text)) {
    await handleScan(chatId, token, ghToken);
  } else if (text === "/status") {
    await handleStatus(chatId, token, ghToken);
  } else if (text === "/stats") {
    await handleStats(chatId, token, ghToken);
  } else if (text === "/help") {
    await handleHelp(chatId, token);
  }
}

// ── Worker entry point ────────────────────────────────────────────────────────
export default {
  async fetch(request, env) {
    if (request.method !== "POST") return new Response("OK");
    try {
      const update = await request.json();
      await handleUpdate(update, env);
    } catch (e) {
      console.error(e);
    }
    return new Response("OK");
  },
};
