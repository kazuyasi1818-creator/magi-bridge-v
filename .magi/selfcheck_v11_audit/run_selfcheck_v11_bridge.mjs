import fs from 'node:fs';
import crypto from 'node:crypto';
const BASE='https://magi-bridge-v4.vercel.app/api/step';
const FX=160, CAP_YEN=90; let spentUsd=0;
const dir='.magi/selfcheck_v11_audit';
const expected={
  'T009R_expected_manifest_selfcheck_v1_1.py':'70c48e722df9704ba2976111ce44d5e02b5775fddedab33f44b1d78e81c31833',
  'test_T009R_expected_manifest_selfcheck_v1_1_adversarial.py':'5feb1eb4ac464190a938862783d3c642b9fe1d40c85d9b4d9b64ffcccfbafea9',
  'T009R_expected_manifest_selfcheck_v1_1_selftest_report.json':'501ca04120a175886c7b2c96f4eb38ad4e1f9795212f399e3a22920a8a79e7a2'
};
const sha=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');
const raw={};
for(const [name,want] of Object.entries(expected)){
  const content=fs.readFileSync(`${dir}/${name}`,'utf8');
  const got=sha(content);
  if(got!==want) throw new Error(`EVIDENCE_HASH_MISMATCH ${name} got=${got} want=${want}`);
  raw[name]=content;
}
const hardening=fs.readFileSync(`${dir}/T009R_selfcheck_v1_1_hardening_report.json`,'utf8');
const hardeningObj=JSON.parse(hardening);
if(hardeningObj?.artifacts?.selfcheck_v1_1?.sha256!==expected['T009R_expected_manifest_selfcheck_v1_1.py']) throw new Error('HARDENING_BINDING_MISMATCH selfcheck');
if(hardeningObj?.artifacts?.selfcheck_test?.sha256!==expected['test_T009R_expected_manifest_selfcheck_v1_1_adversarial.py']) throw new Error('HARDENING_BINDING_MISMATCH test');
if(hardeningObj?.artifacts?.selfcheck_report?.sha256!==expected['T009R_expected_manifest_selfcheck_v1_1_selftest_report.json']) throw new Error('HARDENING_BINDING_MISMATCH report');
if(hardeningObj?.lock_status!=='PROHIBITED' || hardeningObj?.scientific_thresholds_or_gates_changed!==false) throw new Error('GOVERNANCE_STATUS_MISMATCH');
const evidence=[
 {name:'T009R_expected_manifest_selfcheck_v1_1.txt',type:'text/plain',content:raw['T009R_expected_manifest_selfcheck_v1_1.py']},
 {name:'test_T009R_expected_manifest_selfcheck_v1_1_adversarial.txt',type:'text/plain',content:raw['test_T009R_expected_manifest_selfcheck_v1_1_adversarial.py']},
 {name:'T009R_expected_manifest_selfcheck_v1_1_selftest_report.json',type:'application/json',content:raw['T009R_expected_manifest_selfcheck_v1_1_selftest_report.json']},
 {name:'T009R_selfcheck_v1_1_hardening_report.json',type:'application/json',content:hardening}
].map(e=>({...e,size:Buffer.byteLength(e.content),client_sha256:sha(e.content)}));
const totalChars=evidence.reduce((a,e)=>a+e.content.length,0);
const topic=`T009R expected-manifest selfcheck v1.1 independent adversarial re-audit. Audit the ACTUAL supplied source (SHA 70c48e72...c31833), ACTUAL adversarial test source (SHA 5feb1eb4...bafea9), and ACTUAL 12-case report (SHA 501ca041...a79e7a2). Do not trust the report merely because it says PASS: read code and tests. Previous v1 conditional FAIL was: non-object top-level input could pass exact_keys failure then crash on obj.get, producing exit1/no JSON; main only guarded json.loads; invalid input and internal checker failure were not separated. Verify v1.1 now: (1) top-level list/number/string/null fail closed at exact_keys boundary, exit2, JSON evidence written; (2) partitions list and feasibility null yield exit2, not exception; (3) invalid JSON yields exit2 with anchored manifest byte SHA; (4) unexpected internal validator exceptions are separated as exit3 and attempt to preserve PROTOCOL_INVALID JSON evidence; (5) valid manifest still PASS; (6) FULL=A+B arithmetic checks remain intact; (7) test harness actually asserts output existence and correct exit/error classes rather than merely subprocess completion. Also attack the NEW exception/evidence-writing paths and identify any fail-open or evidence-loss path introduced by hardening. Scope is validator hardening only; this is NOT trial/prereg LOCK approval. Actual prospective manifest does not yet exist, LOCK must remain PROHIBITED, A/B not started. Return PASS only if code-level hardening is sound; otherwise REVISE with specific reproducible flaw.`;
async function step(payload){
 const remaining=Math.max(0,CAP_YEN-spentUsd*FX); if(remaining<=0) throw new Error('BUDGET_CAP');
 const r=await fetch(BASE,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...payload,budget_remaining_yen:remaining,budget_fx_yen_per_usd:FX})});
 const t=await r.text(); let d; try{d=JSON.parse(t)}catch{throw new Error(`NON_JSON_${r.status}:${t.slice(0,300)}`)}
 if(!r.ok) throw new Error(d.error||`HTTP_${r.status}`); if(d.usage?.usd!=null) spentUsd+=Number(d.usage.usd||0); return d;
}
const transcript=[]; const push=d=>transcript.push({stage:d.stage,speaker:d.speaker,model:d.model,text:d.text,structured:d.structured||null,usage:d.usage||null,evidence:d.evidence||null});
try{
 let g=await step({stage:'gpt_initial',topic,evidence});push(g);
 let a=await step({stage:'claude_audit',topic,previous:g.text,evidence});push(a);
 g=await step({stage:'gpt_revise',topic,previous:g.text,audit:a.text,evidence});push(g);
 let v=await step({stage:'claude_verdict',topic,previous:g.text,evidence});push(v);
 const out={run_kind:'T009R_SELFCHECK_V1_1_INDEPENDENT_REAUDIT',production_url:BASE,evidence:evidence.map(e=>({name:e.name,sha256:e.client_sha256,chars:e.content.length})),evidence_total_chars:totalChars,spent_usd:spentUsd,spent_yen:spentUsd*FX,final_structured:v?.structured||null,transcript,completed_at:new Date().toISOString()};
 fs.writeFileSync('selfcheck_v11_bridge_result.json',JSON.stringify(out,null,2)); console.log(JSON.stringify(out,null,2));
}catch(err){
 const out={run_kind:'T009R_SELFCHECK_V1_1_INDEPENDENT_REAUDIT',error:String(err?.stack||err),spent_usd:spentUsd,spent_yen:spentUsd*FX,transcript,completed_at:new Date().toISOString()};
 fs.writeFileSync('selfcheck_v11_bridge_result.json',JSON.stringify(out,null,2)); console.error(JSON.stringify(out,null,2)); process.exit(1);
}
