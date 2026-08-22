import stepHandler from '../api/step.js';

function invoke(body) {
  return new Promise((resolve, reject) => {
    const req = { method: 'POST', body };
    const res = {
      statusCode: 200,
      headers: {},
      setHeader(k, v) { this.headers[String(k).toLowerCase()] = v; },
      end(payload) {
        try { resolve({ status: this.statusCode, body: JSON.parse(String(payload || '{}')) }); }
        catch (e) { reject(e); }
      }
    };
    Promise.resolve(stepHandler(req, res)).catch(reject);
  });
}

if (!process.env.ANTHROPIC_API_KEY) throw new Error('ANTHROPIC_API_KEY unavailable in Vercel build environment');

const rejectCase = await invoke({
  stage: 'claude_verdict',
  topic: 'MAGI Bridge v4.4 最終E2Eテスト。架空ケース: OOS 60レースでROI 105%、リークなし、控除率込み。ただし期間安定性と買い目耐性は未検証。さらにOOS結果を確認した後に閾値を調整したところROI 120%になった。この結果だけで本番採用PASSへ昇格してよいか。',
  previous: '最終提案: OOS確認後の閾値調整でROIが120%まで改善したため、この120%を根拠に本番採用PASSへ昇格してよい。期間安定性と買い目耐性は未検証だが、ROI改善を優先して採用する。'
});
const r = rejectCase.body?.structured || {};
console.log('REJECT_RESULT', JSON.stringify({status: rejectCase.status, verdict: r.reported_verdict, revision_class: r.revision_class, human_action_required: r.human_action_required, parse_error: r.parse_error, bridge_version: rejectCase.body?.bridge_version, model: rejectCase.body?.model}));
if (rejectCase.status !== 200) throw new Error(`Reject case HTTP ${rejectCase.status}`);
if (r.reported_verdict !== 'REJECT') throw new Error(`Reject case verdict=${r.reported_verdict}`);
if (r.parse_error !== false) throw new Error(`Reject case parse_error=${r.parse_error}`);
if (JSON.stringify(rejectCase.body).includes('Structured verdict parse failed')) throw new Error('Reject case still contains Structured verdict parse failed');

const passCase = await invoke({
  stage: 'claude_verdict',
  topic: '2+2=4だけ監査',
  previous: '標準自然数の算術において2+2=4である。本案は追加修正不要で確定可能。'
});
const p = passCase.body?.structured || {};
console.log('PASS_RESULT', JSON.stringify({status: passCase.status, verdict: p.reported_verdict, revision_class: p.revision_class, human_action_required: p.human_action_required, parse_error: p.parse_error, bridge_version: passCase.body?.bridge_version, model: passCase.body?.model}));
if (passCase.status !== 200) throw new Error(`Pass case HTTP ${passCase.status}`);
if (p.reported_verdict !== 'PASS') throw new Error(`Pass case verdict=${p.reported_verdict}`);
if (p.revision_class !== 'NONE') throw new Error(`Pass case revision_class=${p.revision_class}`);
if (p.human_action_required !== false) throw new Error(`Pass case human_action_required=${p.human_action_required}`);
if (p.parse_error !== false) throw new Error(`Pass case parse_error=${p.parse_error}`);
if (JSON.stringify(passCase.body).includes('Structured verdict parse failed')) throw new Error('Pass case still contains Structured verdict parse failed');

console.log('MAGI_LIVE_E2E=PASS');
