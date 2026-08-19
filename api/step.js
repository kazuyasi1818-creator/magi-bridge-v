const OPENAI_API = "https://api.openai.com/v1/responses";
const ANTHROPIC_API = "https://api.anthropic.com/v1/messages";

// 2026-08-18 時点の標準API価格（USD / 1M tokens）。
// 料金改定時はここを更新してください。
const OPENAI_PRICES = {
  "gpt-4.1": { input: 2.0, cached: 0.5, output: 8.0 },
  "gpt-5.6": { input: 5.0, cached: 0.5, output: 30.0 },
  "gpt-5.6-sol": { input: 5.0, cached: 0.5, output: 30.0 },
  "gpt-5.6-terra": { input: 2.5, cached: 0.25, output: 15.0 },
  "gpt-5.6-luna": { input: 1.0, cached: 0.1, output: 6.0 },
};

const ANTHROPIC_PRICES = {
  "claude-sonnet-4-6": { input: 3.0, cacheWrite: 3.75, cacheRead: 0.30, output: 15.0 },
  "claude-sonnet-4-5": { input: 3.0, cacheWrite: 3.75, cacheRead: 0.30, output: 15.0 },
};

function send(res, status, body) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.end(JSON.stringify(body));
}

function trim(s, n = 20000) {
  s = String(s || "");
  return s.length > n ? s.slice(-n) : s;
}

function maxTokensFor(stage) {
  const defaults = {
    gpt_initial: 1800,
    claude_audit: 1400,
    gpt_revise: 1800,
    claude_verdict: 800,
  };
  const envKey = {
    gpt_initial: "MAGI_GPT_INITIAL_TOKENS",
    claude_audit: "MAGI_CLAUDE_AUDIT_TOKENS",
    gpt_revise: "MAGI_GPT_REVISE_TOKENS",
    claude_verdict: "MAGI_CLAUDE_VERDICT_TOKENS",
  }[stage];
  const fallback = defaults[stage] || 1200;
  const n = Number((envKey && process.env[envKey]) || fallback);
  return Number.isFinite(n) ? Math.min(Math.max(Math.floor(n), 400), 4000) : fallback;
}

function extractOpenAIText(data) {
  if (typeof data?.output_text === "string" && data.output_text.trim()) return data.output_text.trim();
  const chunks = [];
  for (const item of data?.output || []) {
    for (const content of item?.content || []) {
      if (typeof content?.text === "string") chunks.push(content.text);
    }
  }
  return chunks.join("\n").trim();
}

function extractClaudeText(data) {
  return (data?.content || [])
    .filter((b) => b?.type === "text" && typeof b.text === "string")
    .map((b) => b.text)
    .join("\n")
    .trim();
}

function roundMoney(n) {
  return Math.round((Number(n) || 0) * 1e6) / 1e6;
}

function openAICost(model, usage = {}) {
  const p = OPENAI_PRICES[model];
  const input = Number(usage.input_tokens || 0);
  const output = Number(usage.output_tokens || 0);
  const cached = Number(usage?.input_tokens_details?.cached_tokens || 0);
  const uncached = Math.max(0, input - cached);
  const usd = p ? (uncached * p.input + cached * p.cached + output * p.output) / 1_000_000 : null;
  return {
    provider: "openai",
    input_tokens: input,
    cached_input_tokens: cached,
    output_tokens: output,
    total_tokens: Number(usage.total_tokens || input + output),
    usd: usd == null ? null : roundMoney(usd),
    pricing_known: Boolean(p),
  };
}

function anthropicCost(model, usage = {}) {
  const p = ANTHROPIC_PRICES[model];
  const input = Number(usage.input_tokens || 0);
  const output = Number(usage.output_tokens || 0);
  const cacheWrite = Number(usage.cache_creation_input_tokens || 0);
  const cacheRead = Number(usage.cache_read_input_tokens || 0);
  const usd = p
    ? (input * p.input + cacheWrite * p.cacheWrite + cacheRead * p.cacheRead + output * p.output) / 1_000_000
    : null;
  return {
    provider: "anthropic",
    input_tokens: input,
    cache_write_tokens: cacheWrite,
    cache_read_tokens: cacheRead,
    output_tokens: output,
    total_tokens: input + cacheWrite + cacheRead + output,
    usd: usd == null ? null : roundMoney(usd),
    pricing_known: Boolean(p),
  };
}

async function callOpenAI(prompt, maxOutputTokens) {
  const key = process.env.OPENAI_API_KEY;
  if (!key) throw new Error("OPENAI_API_KEY が未設定です");
  const model = process.env.OPENAI_MODEL || "gpt-4.1";
  const response = await fetch(OPENAI_API, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${key}` },
    body: JSON.stringify({ model, input: prompt, max_output_tokens: maxOutputTokens }),
  });
  const raw = await response.text();
  let data = {};
  try { data = JSON.parse(raw); } catch {}
  if (!response.ok) throw new Error(`OpenAI API (${response.status}): ${data?.error?.message || raw || response.statusText}`);
  const text = extractOpenAIText(data);
  if (!text) throw new Error("OpenAI API からテキストを取得できませんでした");
  return { text, model, usage: openAICost(model, data.usage || {}) };
}

async function callClaude(prompt, maxOutputTokens) {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error("ANTHROPIC_API_KEY が未設定です");
  const model = process.env.ANTHROPIC_MODEL || "claude-sonnet-4-6";
  const response = await fetch(ANTHROPIC_API, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model,
      max_tokens: maxOutputTokens,
      messages: [{ role: "user", content: prompt }],
    }),
  });
  const raw = await response.text();
  let data = {};
  try { data = JSON.parse(raw); } catch {}
  if (!response.ok) throw new Error(`Anthropic API (${response.status}): ${data?.error?.message || raw || response.statusText}`);
  const text = extractClaudeText(data);
  if (!text) throw new Error("Anthropic API からテキストを取得できませんでした");
  return { text, model, usage: anthropicCost(model, data.usage || {}) };
}

function rules(topic) {
  return `研究テーマ: ${topic}\n\n共通ルール:\n- 事実、推測、未検証の仮説を分ける。\n- 数字で検証可能にする。\n- 反証条件を書く。\n- 競馬・投資・暗号資産は利益を保証せず、バックテスト、コスト、スリッページ、最大ドローダウンを重視する。\n- 自動売買・自動購入は行わず研究・意思決定支援に限定する。`;
}

export default async function handler(req, res) {
  if (req.method !== "POST") return send(res, 405, { error: "POST only" });
  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
    const topic = String(body.topic || "").trim();
    const stage = String(body.stage || "");
    const previous = trim(body.previous);
    const audit = trim(body.audit);
    if (!topic) return send(res, 400, { error: "topic は必須です" });
    if (topic.length > 6000) return send(res, 400, { error: "topic が長すぎます" });
    const base = rules(topic);

    let result;
    let speaker;

    if (stage === "gpt_initial") {
      result = await callOpenAI(`${base}\n\nあなたはMAGIの主担当。最初の仮説・分析案を作れ。最後に「検証すべき項目」を箇条書きで示す。`, maxTokensFor(stage));
      speaker = "GPT / 主担当";
    } else if (stage === "claude_audit") {
      if (!previous) return send(res, 400, { error: "previous が必要です" });
      result = await callClaude(`${base}\n\nあなたはMAGIの監査役。以下のGPT案を厳しく批判し、見落とし、データ漏洩、過学習、楽観バイアス、コスト無視、因果と相関の混同を探せ。改善案と反証テストも示せ。冗長な一般論は避け、重要度順にまとめる。\n\nGPT案:\n${previous}`, maxTokensFor(stage));
      speaker = "Claude / 監査";
    } else if (stage === "gpt_revise") {
      if (!previous || !audit) return send(res, 400, { error: "previous と audit が必要です" });
      result = await callOpenAI(`${base}\n\nあなたはMAGIの主担当。Claude監査を受けて案を修正せよ。反論できる点は根拠つきで反論し、妥当な批判は取り入れる。「採用」「保留」「却下」で次の検証項目を整理する。最後まで文章を完成させ、途中で項目を切らない。\n\n直前のGPT案:\n${previous}\n\nClaude監査:\n${audit}`, maxTokensFor(stage));
      speaker = "GPT / 改訂";
    } else if (stage === "claude_verdict") {
      if (!previous) return send(res, 400, { error: "previous が必要です" });
      result = await callClaude(`${base}\n\nあなたは最終判定役。以下の最終GPT案を100点満点で採点する。出力は日本語で900文字程度以内を目安に、必ず次の4項目だけを簡潔に示せ。1)現時点の結論 2)最大の弱点3つ 3)次に取るべきデータ 4)実運用に進める条件。重複説明、長い前置き、表は不要。\n\n最終GPT案:\n${trim(previous, 12000)}`, maxTokensFor(stage));
      speaker = "Claude / 最終監査";
    } else {
      return send(res, 400, { error: "stage が不正です" });
    }

    return send(res, 200, {
      ok: true,
      stage,
      speaker,
      text: result.text,
      model: result.model,
      usage: result.usage,
      pricing_date: "2026-08-18",
    });
  } catch (error) {
    console.error("MAGI step error:", error?.message || error);
    return send(res, 500, { error: error?.message || "Unknown error" });
  }
}
