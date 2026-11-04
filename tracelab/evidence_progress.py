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


def explain_precheck(payload,history,required,analysis):
    p=evidence_progress(payload,history,required)
    claims=analysis.get('claims',[]) if isinstance(analysis,dict) else []
    cited={c['evidence_id'] for claim in claims for c in claim.get('citations',[])}
    mentioned={k for c in claims for k in c.get('metric_ids',[])}
    mentioned.update(a['fact_id'] for c in claims for a in c.get('amounts',[]))
    all_coverage=evidence_progress(payload,history,sorted(set(required)|mentioned))
    p.update(cited_evidence_ids=sorted(cited),ineligible_citation_ids=sorted(cited-set(p['eligible_evidence_ids'])),
             missing_claim_metric_ids=[k for k in all_coverage['missing_core_metric_ids'] if k in mentioned])
    p['ready']=not(p['missing_core_metric_ids'] or p['ineligible_citation_ids'] or p['missing_claim_metric_ids'])
    return p
