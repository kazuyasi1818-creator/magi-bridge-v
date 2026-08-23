import fs from 'node:fs';
import crypto from 'node:crypto';

const BASE='https://magi-bridge-v4.vercel.app/api/step';
const FX=160;
const CAP_YEN=60;
let spentUsd=0;
const dir='.magi/temp_bridge_audit/selfcheck_v11';
const files=[
  'T009R_expected_manifest_selfcheck_v1_1.py',
  'test_T009R_expected_manifest_selfcheck_v1_1_adversarial.py',
  'T009R_expected_manifest_selfcheck_v1_1_selftest_report.json',
  'T009R_checker_C_v3_1_to_v3_1_1.patch',
  'T009R_selfcheck_v1_1_hardening_report.json'
];
const sha=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');
const evidence=files.map(name=>{const content=fs.readFileSync(`${dir}/${name}`,'utf8');return{name,type:name.endsWith('.json')?'application/json':'text/plain',size:Buffer.byteLength(content),content,client_sha256:sha(content)}});
const topic=`T009R expected-manifest selfcheck v1.1 と Checker C v3.1.1差分をLOCK前に独立再監査する。前回指摘の答え合わせだけでなくゼロベースで新しい攻撃面を探す。重点: (1) selfcheckトップレベル非dict/list/number/string/nullで必ずexit2+JSON証跡、(2) partitions list / feasibility nullでexit2+JSON、(3)予期しないvalidator内部例外はexit3+PROTOCOL_INVALID JSON証跡、(4) exact_keys false後に危険な .get() を続行しないこと、(5) manifest自己整合FULL=A+Bの維持、(6) Checker C v3.1→v3.1.1はnoniterable partition_set分類hardeningのみで科学閾値/Gate/verdict条件を変更していないこと。GitHub Actionsでselfcheck adversarial suiteを実行し12/12 PASSした同一artifactを証拠として渡している。LOCK承認ではない。実prospective expected manifestは未収集、A/B implementationは未着手、LOCK禁止を維持する。問題があれば具体的な反証入力/コード箇所/修正方針を返す。`;
async function step(payload){
 const rem=Math.max(0,CAP_YEN-spentUsd*FX); if(rem<=0) throw new Error('BUDGET_CAP');
 const r=await fetch(BASE,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...payload,budget_remaining_yen:rem,budget_fx_yen_per_usd:FX})});
 const raw=await r.text(); let d; try{d=JSON.parse(raw)}catch{throw new Error(`NON_JSON_${r.status}:${raw.slice(0,500)}`)}
 if(!r.ok) throw new Error(d.error||`HTTP_${r.status}`); if(d.usage?.usd!=null) spentUsd+=Number(d.usage.usd||0); return d;
}
const transcript=[]; const push=d=>transcript.push({stage:d.stage,speaker:d.speaker,model:d.model,text:d.text,structured:d.structured||null,usage:d.usage||null,evidence:d.evidence||null});
try{
 let g=await step({stage:'gpt_initial',topic,evidence});push(g);
 let a=await step({stage:'claude_audit',topic,previous:g.text,evidence});push(a);
 g=await step({stage:'gpt_revise',topic,previous:g.text,audit:a.text,evidence});push(g);
 let v=await step({stage:'claude_verdict',topic,previous:g.text,evidence});push(v);
 let auto=0;const fixable=new Set(['REPORTING_OR_INFERENCE','EVIDENCE_RECONCILIATION']);
 while(v?.structured?.reported_verdict==='REVISE'&&!v?.structured?.human_action_required&&fixable.has(v?.structured?.revision_class)&&auto<2){auto++;g=await step({stage:'gpt_revise',topic,previous:g.text,audit:v.text,evidence});push(g);v=await step({stage:'claude_verdict',topic,previous:g.text,evidence});push(v)}
 const out={run_kind:'T009R_SELFCHECK_V1_1_CHECKER_V3_1_1_REAUDIT',production_url:BASE,evidence:evidence.map(e=>({name:e.name,sha256:e.client_sha256,chars:e.content.length})),spent_usd:spentUsd,spent_yen:spentUsd*FX,auto_revisions:auto,final_structured:v?.structured||null,transcript,completed_at:new Date().toISOString()};
 fs.writeFileSync('selfcheck_v11_bridge_result.json',JSON.stringify(out,null,2));console.log(JSON.stringify(out,null,2));
}catch(err){const out={run_kind:'T009R_SELFCHECK_V1_1_CHECKER_V3_1_1_REAUDIT',error:String(err?.stack||err),spent_usd:spentUsd,spent_yen:spentUsd*FX,transcript,completed_at:new Date().toISOString()};fs.writeFileSync('selfcheck_v11_bridge_result.json',JSON.stringify(out,null,2));console.error(JSON.stringify(out,null,2));process.exit(1)}
