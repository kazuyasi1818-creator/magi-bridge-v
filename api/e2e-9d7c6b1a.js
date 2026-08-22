import stepHandler from './step.js';

function invoke(body) {
  return new Promise((resolve, reject) => {
    const req = { method: 'POST', body };
    const res = {
      statusCode: 200,
      headers: {},
      setHeader(k, v) { this.headers[String(k).toLowerCase()] = v; },
      end(payload) {
        try {
          resolve({ status: this.statusCode, body: JSON.parse(String(payload || '{}')) });
        } catch (e) { reject(e); }
      }
    };
    Promise.resolve(stepHandler(req, res)).catch(reject);
  });
}

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.statusCode = 405;
    res.setHeader('content-type', 'application/json; charset=utf-8');
    return res.end(JSON.stringify({ error: 'GET only' }));
  }
  try {
    const rejectCase = await invoke({
      stage: 'claude_verdict',
      topic: 'MAGI Bridge v4.4 最終E2Eテスト。架空ケース: OOS 60レースでROI 105%、リークなし、控除率込み。ただし期間安定性と買い目耐性は未検証。さらにOOS結果を確認した後に閾値を調整したところROI 120%になった。この結果だけで本番採用PASSへ昇格してよいか。',
      previous: '最終提案: OOS確認後の閾値調整でROIが120%まで改善したため、この120%を根拠に本番採用PASSへ昇格してよい。期間安定性と買い目耐性は未検証だが、ROI改善を優先して採用する。'
    });
    const passCase = await invoke({
      stage: 'claude_verdict',
      topic: '2+2=4だけ監査',
      previous: '標準自然数の算術において2+2=4である。本案は追加修正不要で確定可能。'
    });
    const r = rejectCase.body?.structured || {};
    const p = passCase.body?.structured || {};
    const ok = rejectCase.status === 200 && passCase.status === 200 &&
      r.reported_verdict === 'REJECT' && r.parse_error === false &&
      p.reported_verdict === 'PASS' && p.revision_class === 'NONE' &&
      p.human_action_required === false && p.parse_error === false;
    res.statusCode = ok ? 200 : 500;
    res.setHeader('content-type', 'application/json; charset=utf-8');
    return res.end(JSON.stringify({ ok, reject_case: rejectCase, pass_case: passCase }));
  } catch (error) {
    res.statusCode = 500;
    res.setHeader('content-type', 'application/json; charset=utf-8');
    return res.end(JSON.stringify({ ok: false, error: error?.message || String(error) }));
  }
}
