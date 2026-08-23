import stepHandler from "./step.js";

function runStep(body) {
  return new Promise((resolve) => {
    const req = { method: "POST", body };
    const headers = {};
    const res = {
      statusCode: 200,
      setHeader(k, v) { headers[k] = v; },
      end(payload) {
        let parsed = null;
        try { parsed = JSON.parse(String(payload || "")); } catch {}
        resolve({ statusCode: this.statusCode, headers, body: parsed });
      }
    };
    Promise.resolve(stepHandler(req, res)).catch((error) => {
      resolve({ statusCode: 500, headers, body: { error: error?.message || String(error) } });
    });
  });
}

export default async function handler(req, res) {
  if (req.method !== "GET") {
    res.statusCode = 405;
    res.setHeader("content-type", "application/json; charset=utf-8");
    return res.end(JSON.stringify({ ok: false, error: "GET only" }));
  }

  const reject = await runStep({
    stage: "claude_verdict",
    topic: "MAGI Bridge v4.4 最終E2Eテスト。架空ケース: OOS 60レースでROI 105%、リークなし、控除率込み。ただし期間安定性と買い目耐性は未検証。さらにOOS結果を確認した後に閾値を調整したところROI 120%になった。この結果だけで本番採用PASSへ昇格してよいか。",
    previous: "最終提案: OOS確認後の閾値調整でROIが120%まで改善したため、この120%を根拠に本番採用PASSへ昇格してよい。期間安定性と買い目耐性は未検証だが、ROI改善を優先して採用する。"
  });

  const pass = await runStep({
    stage: "claude_verdict",
    topic: "2+2=4だけ監査",
    previous: "標準自然数の算術において2+2=4である。本案は追加修正不要で確定可能。"
  });

  const rs = reject.body?.structured || {};
  const ps = pass.body?.structured || {};
  const rejectOk = reject.statusCode === 200 && rs.reported_verdict === "REJECT" && rs.parse_error === false && !JSON.stringify(reject.body).includes("Structured verdict parse failed");
  const passOk = pass.statusCode === 200 && ps.reported_verdict === "PASS" && ps.revision_class === "NONE" && ps.human_action_required === false && ps.parse_error === false && !JSON.stringify(pass.body).includes("Structured verdict parse failed");

  res.statusCode = rejectOk && passOk ? 200 : 500;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.end(JSON.stringify({
    ok: rejectOk && passOk,
    reject: {
      http: reject.statusCode,
      reported_verdict: rs.reported_verdict || null,
      revision_class: rs.revision_class || null,
      human_action_required: rs.human_action_required ?? null,
      parse_error: rs.parse_error ?? null,
      bridge_version: reject.body?.bridge_version || null,
      model: reject.body?.model || null,
      error: reject.body?.error || null
    },
    pass: {
      http: pass.statusCode,
      reported_verdict: ps.reported_verdict || null,
      revision_class: ps.revision_class || null,
      human_action_required: ps.human_action_required ?? null,
      parse_error: ps.parse_error ?? null,
      bridge_version: pass.body?.bridge_version || null,
      model: pass.body?.model || null,
      error: pass.body?.error || null
    }
  }));
}
