import fs from 'node:fs';
import crypto from 'node:crypto';

const BASE = 'https://magi-bridge-v4.vercel.app/api/step';
const FX = 160;
const CAP_YEN = 50;
let spentUsd = 0;
const dir = '.magi/temp_bridge_audit';
const files = [
  'T009R_checker_C_v2_candidate.py',
  'T009R_checker_C_self_audit_v1_to_v2.json',
  'T009R_CheckerC_Audit_Context_from_Prereg_v0.4.json'
];
const sha = s => crypto.createHash('sha256').update(s, 'utf8').digest('hex');
const evidence = files.map(name => {
  const content = fs.readFileSync(`${dir}/${name}`, 'utf8');
  return {name, type: name.endsWith('.py') ? 'text/plain' : 'application/json', size: Buffer.byteLength(content), content, client_sha256: sha(content)};
});
const topic = `T009R confirmatory trialのChecker C v2 candidateをLOCK前に敵対的監査する。提示コードを実際に読んで、共有バグ・schema抜け・precedence bug・hash/canonicalization穴・bootstrap/verdict再計算の矛盾・zero-event処理・prereg v0.4との不一致を探す。自己監査を鵜呑みにせず、LOCK可能か判定する。修正が必要なら具体的なコード箇所と修正方針を示す。新holdout結果は使わず、ガバナンス変更やGate緩和は禁止。`;

async function step(payload){
  const remaining = Math.max(0, CAP_YEN - spentUsd * FX);
  if (remaining <= 0) throw new Error('BUDGET_CAP');
  const r = await fetch(BASE, {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({...payload, budget_remaining_yen: remaining, budget_fx_yen_per_usd: FX})});
  const raw = await r.text();
  let d;
  try { d = JSON.parse(raw); } catch { throw new Error(`NON_JSON_${r.status}:${raw.slice(0,500)}`); }
  if (!r.ok) throw new Error(d.error || `HTTP_${r.status}`);
  if (d.usage?.usd != null) spentUsd += Number(d.usage.usd || 0);
  return d;
}

const transcript=[];
function push(d){ transcript.push({stage:d.stage,speaker:d.speaker,model:d.model,text:d.text,structured:d.structured||null,usage:d.usage||null,evidence:d.evidence||null}); }

try {
  let g = await step({stage:'gpt_initial',topic,evidence}); push(g);
  let a = await step({stage:'claude_audit',topic,previous:g.text,evidence}); push(a);
  g = await step({stage:'gpt_revise',topic,previous:g.text,audit:a.text,evidence}); push(g);
  let v = await step({stage:'claude_verdict',topic,previous:g.text,evidence}); push(v);
  let auto=0;
  const fixable = new Set(['REPORTING_OR_INFERENCE','EVIDENCE_RECONCILIATION']);
  while (v?.structured?.reported_verdict === 'REVISE' && !v?.structured?.human_action_required && fixable.has(v?.structured?.revision_class) && auto < 2) {
    auto++;
    g = await step({stage:'gpt_revise',topic,previous:g.text,audit:v.text,evidence}); push(g);
    v = await step({stage:'claude_verdict',topic,previous:g.text,evidence}); push(v);
  }
  const out = {
    run_kind:'TEMP_BRANCH_DIRECT_PRODUCTION_BRIDGE_AUDIT',
    production_url:'https://magi-bridge-v4.vercel.app',
    topic,
    evidence:evidence.map(e=>({name:e.name,sha256:e.client_sha256,chars:e.content.length})),
    spent_usd:spentUsd,
    spent_yen:spentUsd*FX,
    auto_revisions:auto,
    final_structured:v?.structured||null,
    transcript,
    completed_at:new Date().toISOString()
  };
  fs.writeFileSync('bridge_result.json', JSON.stringify(out,null,2));
  console.log(JSON.stringify(out,null,2));
} catch (err) {
  const out={run_kind:'TEMP_BRANCH_DIRECT_PRODUCTION_BRIDGE_AUDIT',error:String(err?.stack||err),spent_usd:spentUsd,spent_yen:spentUsd*FX,transcript,completed_at:new Date().toISOString()};
  fs.writeFileSync('bridge_result.json', JSON.stringify(out,null,2));
  console.error(JSON.stringify(out,null,2));
  process.exit(1);
}
