import fs from 'node:fs';
import crypto from 'node:crypto';

const BASE = 'https://magi-bridge-v4.vercel.app/api/step';
const FX = 160;
const CAP_YEN = 50;
let spentUsd = 0;
const dir = '.magi/temp_bridge_audit';
const defs = [
  {path:'T009R_checker_C_v3_candidate.py', name:'T009R_checker_C_v3_candidate.txt', type:'text/plain'},
  {path:'T009R_checker_C_v3_remediation_report.json', name:'T009R_checker_C_v3_remediation_report.json', type:'application/json'},
  {path:'T009R_CheckerC_Audit_Context_from_Prereg_v0.4.json', name:'T009R_CheckerC_Audit_Context_from_Prereg_v0.4.json', type:'application/json'}
];
const sha = s => crypto.createHash('sha256').update(s,'utf8').digest('hex');
const evidence = defs.map(d => {
  const content = fs.readFileSync(`${dir}/${d.path}`,'utf8');
  return {name:d.name,type:d.type,size:Buffer.byteLength(content),content,client_sha256:sha(content)};
});
const topic = `前回のMAGI Bridge Claude監査でChecker C v2に指摘されたBug #1 seed三項演算子、Bug #2 invalid implementation ID後のvalidation継続、Bug #3 schema違反後の継続リスクを修正したChecker C v3 candidateを再監査する。さらにChatGPTが追加で見つけたmalformed expected_manifest時のfail-closed不足も修正済み。remediation reportの機械テスト結果を鵜呑みにせずコードを直接読んで反証する。LOCK可否はまだdry-run等の既存Gateを緩めず判断する。`;
async function step(payload){
  const remaining=Math.max(0,CAP_YEN-spentUsd*FX);
  if(remaining<=0) throw new Error('BUDGET_CAP');
  const r=await fetch(BASE,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...payload,budget_remaining_yen:remaining,budget_fx_yen_per_usd:FX})});
  const raw=await r.text(); let d;
  try{d=JSON.parse(raw)}catch{throw new Error(`NON_JSON_${r.status}:${raw.slice(0,500)}`)}
  if(!r.ok) throw new Error(d.error||`HTTP_${r.status}`);
  if(d.usage?.usd!=null) spentUsd+=Number(d.usage.usd||0);
  return d;
}
const transcript=[];
const push=d=>transcript.push({stage:d.stage,speaker:d.speaker,model:d.model,text:d.text,structured:d.structured||null,usage:d.usage||null,evidence:d.evidence||null});
try{
  const g=await step({stage:'gpt_initial',topic,evidence}); push(g);
  const a=await step({stage:'claude_audit',topic,previous:g.text,evidence}); push(a);
  const out={run_kind:'TEMP_BRANCH_BRIDGE_FOLLOWUP_TWO_TURNS',topic,evidence:evidence.map(e=>({name:e.name,sha256:e.client_sha256,chars:e.content.length})),spent_usd:spentUsd,spent_yen:spentUsd*FX,transcript,completed_at:new Date().toISOString()};
  fs.writeFileSync('bridge_followup_result.json',JSON.stringify(out,null,2));
  console.log(JSON.stringify(out,null,2));
}catch(err){
  const out={run_kind:'TEMP_BRANCH_BRIDGE_FOLLOWUP_TWO_TURNS',error:String(err?.stack||err),spent_usd:spentUsd,spent_yen:spentUsd*FX,transcript,completed_at:new Date().toISOString()};
  fs.writeFileSync('bridge_followup_result.json',JSON.stringify(out,null,2));
  console.error(JSON.stringify(out,null,2)); process.exit(1);
}
