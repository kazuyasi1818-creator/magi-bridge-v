#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from datetime import datetime
from pathlib import Path


def parse_ts(s: str) -> datetime:
    x = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    if x.tzinfo is None or x.utcoffset() is None:
        raise ValueError(f'offset-aware timestamp required: {s}')
    return x


def load_plan(path: Path):
    rows = []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        required = {'race_id','horse_no','snapshot_role','prediction_snapshot_time_jst'}
        if not required.issubset(set(r.fieldnames or [])):
            raise ValueError(f'snapshot plan requires {sorted(required)}')
        for x in r:
            role = (x['snapshot_role'] or '').strip().upper()
            if role not in {'EARLY','LATE'}:
                raise ValueError(f'invalid snapshot_role: {role}')
            rows.append({
                'race_id': str(x['race_id']).strip(),
                'horse_no': str(x['horse_no']).strip().zfill(2),
                'snapshot_role': role,
                'snapshot_time': parse_ts(x['prediction_snapshot_time_jst']),
                'prediction_snapshot_time_jst': x['prediction_snapshot_time_jst'],
            })
    return rows


def load_captures(root: Path):
    metas = []
    for p in sorted((root / 'RAW_APPEND_ONLY').glob('*/*.json')):
        try:
            m = json.loads(p.read_text(encoding='utf-8-sig'))
            capture_t = parse_ts(m['source_capture_time_jst'])
        except Exception:
            continue
        for rec in m.get('records') or []:
            announce = rec.get('source_announcement_time_jst')
            try:
                announce_t = parse_ts(announce) if announce else None
            except Exception:
                announce_t = None
            metas.append({
                'meta_path': p,
                'capture_id': m.get('capture_id'),
                'dataspec': m.get('dataspec'),
                'capture_time': capture_t,
                'capture_time_text': m.get('source_capture_time_jst'),
                'raw_file': m.get('raw_file'),
                'raw_sha': m.get('raw_file_sha256'),
                'record_sequence': rec.get('record_sequence'),
                'record_id': rec.get('record_id'),
                'record': rec,
                'announce_time': announce_t,
                'announce_time_text': announce,
            })
    return metas


def candidate_rows(captures, plan):
    race_id = plan['race_id']
    horse_no = plan['horse_no']
    snap = plan['snapshot_time']
    scope_key = race_id[:14]
    out = []
    for c in captures:
        if c['capture_time'] > snap:
            continue
        if c['announce_time'] is None or c['announce_time'] > snap:
            continue
        rec = c['record']
        rid = c['record_id']
        if rid == 'WE':
            if str(rec.get('scope_key') or '') != scope_key:
                continue
        else:
            if str(rec.get('race_id') or '') != race_id:
                continue
            if rid in {'WH','AV','JC'}:
                if rid == 'WH':
                    pass
                elif str(rec.get('horse_no') or '').zfill(2) != horse_no:
                    continue
        out.append(c)
    return out


def select_latest(items):
    if not items:
        return None
    return max(items, key=lambda c: (c['announce_time'], c['capture_time'], int(c['record_sequence'] or 0)))


def emit(row_out, plan, c, feature_name, feature_value, source_kind, horse_no=None):
    if feature_value is None or str(feature_value).strip() == '':
        return
    row_out.append({
        'race_id': plan['race_id'],
        'horse_no': horse_no or plan['horse_no'],
        'snapshot_role': plan['snapshot_role'],
        'prediction_snapshot_time_jst': plan['snapshot_time'].isoformat(),
        'feature_name': feature_name,
        'feature_value': feature_value,
        'feature_source_time_jst': c['announce_time'].isoformat(),
        'source_capture_time_jst': c['capture_time'].isoformat(),
        'source_time_basis': 'OFFICIAL_ANNOUNCEMENT',
        'source_kind': source_kind,
        'source_file_sha256': c['raw_sha'],
        'source_row_id': f"{c['capture_id']}:{c['record_sequence']}:{horse_no or plan['horse_no']}",
    })


def build_for_plan(captures, plan):
    rows = []
    candidates = candidate_rows(captures, plan)

    # WH contains an array of horses. Select latest WH record for the race, then the planned horse.
    wh = select_latest([c for c in candidates if c['record_id'] == 'WH'])
    if wh:
        horse = next((h for h in wh['record'].get('horses', []) if str(h.get('horse_no') or '').zfill(2) == plan['horse_no']), None)
        if horse:
            emit(rows, plan, wh, 'body_weight_kg', horse.get('body_weight_kg'), 'JRA_VAN_0B11_WH')
            emit(rows, plan, wh, 'body_weight_change_kg', horse.get('body_weight_change_kg'), 'JRA_VAN_0B11_WH')

    av = select_latest([c for c in candidates if c['record_id'] == 'AV'])
    if av:
        emit(rows, plan, av, 'abnormal_code', av['record'].get('abnormal_code'), 'JRA_VAN_0B14_AV')

    jc = select_latest([c for c in candidates if c['record_id'] == 'JC'])
    if jc:
        emit(rows, plan, jc, 'current_jockey_code', jc['record'].get('current_jockey_code'), 'JRA_VAN_0B14_JC')
        emit(rows, plan, jc, 'current_jockey_name', jc['record'].get('current_jockey_name'), 'JRA_VAN_0B14_JC')
        emit(rows, plan, jc, 'current_carried_weight_x10', jc['record'].get('current_carried_weight_x10'), 'JRA_VAN_0B14_JC')

    tc = select_latest([c for c in candidates if c['record_id'] == 'TC'])
    if tc:
        emit(rows, plan, tc, 'current_post_time', tc['record'].get('current_post_time_hhmm'), 'JRA_VAN_0B14_TC')

    we = select_latest([c for c in candidates if c['record_id'] == 'WE'])
    if we:
        emit(rows, plan, we, 'weather', we['record'].get('weather_code'), 'JRA_VAN_0B14_WE')
        # Keep turf/dirt raw values distinct until surface mapping is frozen by a later prereg.
        # The current contract exposes generic track_condition, so do not guess which surface applies here.

    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--snapshot-plan', required=True)
    ap.add_argument('--out-csv', required=True)
    ap.add_argument('--out-source-manifest', required=True)
    args = ap.parse_args()

    root = Path(args.root)
    plan = load_plan(Path(args.snapshot_plan))
    captures = load_captures(root)
    out = []
    for p in plan:
        out.extend(build_for_plan(captures, p))

    fields = [
        'race_id','horse_no','snapshot_role','prediction_snapshot_time_jst','feature_name','feature_value',
        'feature_source_time_jst','source_capture_time_jst','source_time_basis','source_kind','source_file_sha256','source_row_id'
    ]
    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(out)

    used = {}
    for r in out:
        used[r['source_file_sha256']] = None
    for c in captures:
        if c['raw_sha'] in used:
            used[c['raw_sha']] = c['raw_file']
    manifest = {'sources':[{'path': p, 'sha256': h} for h,p in sorted(used.items()) if p]}
    manifest_path = Path(args.out_source_manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    summary = {
        'builder_id':'KEIBA_BUILD_SNAPSHOT_PROVENANCE_V1',
        'plan_rows':len(plan),
        'capture_records_seen':len(captures),
        'provenance_rows_emitted':len(out),
        'source_files_used':len(manifest['sources']),
        'note':'No outcome/VALIDATION/OOS data used. Missing realtime features remain missing; no backfill from final-state JVD.',
        'validation_oos_opened':False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
