"""Route B: catalogs and initial facts never grant citation eligibility."""
from .source_contract import verified_evidence


def core_metrics(goal, explicit=()):
    # Legacy live plans had no tasks. Preserve their known two-metric goal.
    required=set(explicit)
    if '净利润' in goal and ('经营活动现金流' in goal or '经营现金流' in goal):
        required.update(('net_profit','operating_cashflow'))
    return sorted(required)


def evidence_progress(payload, history, required=()):
    evidence={e['evidence_id']:e for e in payload['evidence']}
    facts={f['fact_id']:f for f in payload['facts']}
    discovered=set();retrieved=set()
    for h in history:
        if h['action']=='search':
            ids={e['evidence_id'] for e in h['result'] if e['evidence_id'] in evidence}
            discovered.update(ids);retrieved.update(ids)
        elif h['action']=='get' and h['arguments'].get('evidence_id') in evidence:
            retrieved.add(h['arguments']['evidence_id'])
    eligible={k for k in retrieved if verified_evidence(evidence[k],payload)}
    coverage={k:sorted(set(facts.get(k,{}).get('evidence_ids',[])) & eligible) for k in required}
    missing=[k for k,v in coverage.items() if not v]
    return dict(authorized_evidence_ids=sorted(evidence),provided_evidence_ids=[],
                discovered_evidence_ids=sorted(discovered),retrieved_evidence_ids=sorted(retrieved),
                eligible_evidence_ids=sorted(eligible),core_metric_ids=list(required),
                core_coverage=coverage,missing_core_metric_ids=missing,
                missing_core_candidate_ids={k:sorted(set(facts.get(k,{}).get('evidence_ids',[])) & set(evidence)) for k in missing},
                provided_evidence_policy='no_initial_original_evidence_in_route_b')


def explain_precheck(payload,history,required,analysis, *, task_progress=None):
    p=evidence_progress(payload,history,required)
    claims=analysis.get('claims',[]) if isinstance(analysis,dict) else []
    cited={c['evidence_id'] for claim in claims for c in claim.get('citations',[])}
    mentioned={k for c in claims for k in c.get('metric_ids',[])}
    mentioned.update(a['fact_id'] for c in claims for a in c.get('amounts',[]))
    all_coverage=evidence_progress(payload,history,sorted(set(required)|mentioned))
    p.update(cited_evidence_ids=sorted(cited),ineligible_citation_ids=sorted(cited-set(p['eligible_evidence_ids'])),
             missing_claim_metric_ids=[k for k in all_coverage['missing_core_metric_ids'] if k in mentioned])
    p['ready']=not(p['missing_core_metric_ids'] or p['ineligible_citation_ids'] or p['missing_claim_metric_ids'])
    if task_progress is not None:
        primary=[r for r in task_progress['tasks'] if r['kind'] in ('fact','disclosure')]
        unresolved=task_progress['unresolved_task_ids']
        p['unfinished_required_task_ids']=[r['task_id'] for r in primary if r['status']!='answered']
        p['planning_gap']=task_progress['planning_gap'] or len(primary)<3
        p['unresolved_task_ids']=unresolved
        p['unresolved_questions_recorded']=not unresolved or bool(analysis.get('questions'))
        p['ready']=p['ready'] and not (p['planning_gap'] or p['unfinished_required_task_ids']) and p['unresolved_questions_recorded']
    return p


def investigation_task_progress(payload, tasks, history, *, budget_exhausted=False):
    """Local task ledger, independent of explanation acceptance and model assertions."""
    from .agent import LocalFacts
    facts=LocalFacts(payload).rows
    evidence={e['evidence_id']:e for e in payload['evidence']}
    eligible=set(evidence_progress(payload,history)['eligible_evidence_ids'])
    rows=[]
    names={'net_profit':'净利润','operating_cashflow':'经营活动产生的现金流量净额'}
    for task in tasks:
        if task.get('kind') not in ('fact','disclosure','reconciliation','gaps'):continue
        ids=task.get('fact_ids',[])
        sources=sorted({eid for fid in ids if fid in facts for eid in facts[fid]['evidence_ids']} & eligible)
        status='pending';reason='not_investigated';answer=None
        missing=[fid for fid in ids if fid not in facts]
        unresolved=list(task['questions'])
        if task['kind']=='fact':
            fid=ids[0];fact=facts.get(fid)
            metadata=(fact and fact['name']==names.get(fid) and len(fact['periods'])==2
                      and payload.get('currency') and payload.get('scope')
                      and all(f in fact['amounts'] and '元' in fact['amounts'][f] for f in ('base','current','change')))
            if metadata and sources:
                status='answered';reason='verified_fact_and_retrieved_bound_source';unresolved=[]
                answer={k:fact[k] for k in ('fact_id','name','periods','amounts')}
                answer.update(scope=payload['scope'],currency=payload['currency'])
            elif missing:status='evidence_gap';reason='authorization_scope_or_unverified_fact'
            elif sources:status='evidence_gap';reason='fact_metadata_incomplete_or_identity_mismatch'
        elif task['kind']=='disclosure':
            # This task only asks what the scoped annual report discloses, not whether it is causal truth.
            e=evidence.get('E07_28');sources=['E07_28'] if 'E07_28' in eligible else []
            if sources and facts.get('operating_cashflow') and e.get('comparison_basis')=='yoy' and '主要系' in e['text']:
                status='answered';reason='annual_report_disclosure_only';unresolved=[]
                answer=dict(evidence_id='E07_28',quote=e['text'],support_limit='仅记录年报定性披露，不证明完整贡献或背离原因')
            elif not e or missing:status='evidence_gap';reason='authorization_scope'
            elif sources:status='evidence_gap';reason='disclosure_support_not_established'
        elif task['kind']=='reconciliation':
            if sources:
                status='evidence_gap';reason='no_verified_reconciliation_assessment'
            unresolved=['缺少净利润到经营现金流的调节及经营解释证据；仅有指标与披露不构成解释']
        else:
            unresolved=[q for r in rows for q in r['unresolved_questions']]
            status='evidence_gap' if any(r['status']=='evidence_gap' for r in rows) else 'pending'
            reason='unresolved_tasks' if unresolved else 'gap_review_pending'
        if budget_exhausted and status!='answered':
            status='evidence_gap'
        rows.append(dict(task_id=task['id'],kind=task['kind'],status=status,reason=reason,
            eligible_evidence_ids=sources,missing_fact_ids=missing,answer=answer,
            candidate_evidence_ids=task.get('candidate_evidence_ids',[]),
            missing_evidence_types=[] if status=='answered' else task.get('required_sources',[]),
            unresolved_questions=unresolved,budget_exhausted=budget_exhausted and status!='answered'))
    return dict(version='v1',tasks=rows,complete=bool(rows) and all(r['status']=='answered' for r in rows),
                planning_gap=not bool(rows),unresolved_task_ids=[r['task_id'] for r in rows if r['status']!='answered'])


def task_decision(progress, eligible_ids, remaining):
    """Compact guidance from the existing ledger; never answers a task itself."""
    primary=[r for r in progress['tasks'] if r['kind'] in ('fact','disclosure')]
    pending=[r for r in primary if r['status']!='answered']
    candidates=sorted({e for r in pending if r['status']=='pending'
                       for e in r['candidate_evidence_ids']} - set(eligible_ids))
    can_investigate=bool(candidates and remaining.get('tool_calls',0)>0 and remaining.get('rounds',0)>1)
    ready=not progress['planning_gap'] and len(primary)>=3 and not pending
    return dict(next_step='limited_explain_or_stop' if ready else 'investigate_or_stop' if can_investigate else 'stop_with_evidence_gap',
                tasks=[dict(task_id=r['task_id'],status=r['status']) for r in progress['tasks']],
                candidate_evidence_ids=candidates if can_investigate else [],
                unresolved_task_ids=progress['unresolved_task_ids'],
                unresolved_questions=list(dict.fromkeys(q for r in progress['tasks'] for q in r['unresolved_questions'])))
