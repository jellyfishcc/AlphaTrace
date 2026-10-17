"""Single structured claim checking. No text extraction, model or network calls."""
import argparse
import json
import re
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path

from .agent import LocalFacts, LocalEvidence
from .source_contract import verified_evidence

UNITS = {'元': Decimal(1), '万元': Decimal(10000), '亿元': Decimal(100000000)}


def check_claim(claim, payload, *, simulation=False):
    """Payload must come from load_agent_payload, not user/model-supplied receipts.

    simulation is reserved for the fixed public demo; it never grants real provenance.
    Structured fields are authoritative; original_text is retained, not parsed.
    """
    result = dict(status='无法核实', simulation=simulation, llm_called=False,
                  claim=claim, errors=[], process=[], sources=[], correction=None)
    def unknown(reason):
        result['process'].append(reason)
        return result
    required = ('company', 'period', 'base_period', 'metric_id', 'metric_name',
                'scope', 'comparison_basis', 'value_kind', 'value', 'unit',
                'direction', 'original_text')
    if not isinstance(claim, dict) or any(not isinstance(claim.get(k), str) or not claim[k] for k in required):
        return unknown('结构化字段缺失或类型不正确')
    if (claim['company'] != payload.get('company') or
        payload.get('periods') != [claim['base_period'], claim['period']] or
        claim['scope'] != payload.get('scope') or claim['comparison_basis'] != 'yoy'):
        return unknown('公司、期间、合并口径或比较基准不匹配')
    if claim['value_kind'] not in ('current', 'change_magnitude'):
        return unknown('仅支持本期金额或同比变化绝对金额')
    if claim['direction'] not in ('增长', '下降', '持平') or claim['unit'] not in UNITS:
        return unknown('方向或单位不受支持')
    if len(claim['value']) > 50 or not re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?', claim['value']):
        return unknown('请使用普通十进制金额字符串')
    try:
        if simulation:
            if payload.get('data_kind') != 'simulated':
                return unknown('模拟入口只接受明确标记的模拟数据')
            fact = next(f for f in payload['facts'] if f['fact_id'] == claim['metric_id'])
            sources = payload['evidence']
        else:
            fact = LocalFacts(payload).get(claim['metric_id'])
            sources = [LocalEvidence(payload).get(eid) for eid in fact['evidence_ids']]
            if not sources or any(not verified_evidence(e, payload) or
                    claim['metric_id'] not in e['related_facts'] or
                    e.get('comparison_basis') not in ('yoy', 'both_periods') for e in sources):
                return unknown('来源缺失、不一致或不支持同比比较')
        if fact['name'] != claim['metric_name']:
            return unknown('指标名称与指标口径不匹配')
        with localcontext() as ctx:
            ctx.prec = 60
            base, current, change = [Decimal(fact['amounts'][k]['元']) for k in ('base', 'current', 'change')]
            value = Decimal(claim['value'])
            if any(not x.is_finite() for x in (base, current, change, value)):
                return unknown('金额必须是有限十进制数')
            if current - base != change:
                return unknown('已有事实两期金额与差额不一致')
            # User's literal precision controls display rounding, never accounting tolerance.
            places = max(0, -value.as_tuple().exponent)
            if places > 8 or (claim['value_kind'] == 'change_magnitude' and value < 0):
                return unknown('展示精度超限或变化绝对金额为负')
            quantum = Decimal(1).scaleb(-places)
            amount = current if claim['value_kind'] == 'current' else abs(change)
            expected = (amount / UNITS[claim['unit']]).quantize(quantum, rounding=ROUND_HALF_UP)
            direction = '增长' if change > 0 else '下降' if change < 0 else '持平'
            result['process'].extend([
                '公司、两期、指标名称、披露合并口径及同比基准匹配',
                '模拟事实（无真实来源核验）' if simulation else '复用可信事实查询与年报来源核验结果',
                f'基期 {base} 元；本期 {current} 元；已有差额 {change} 元',
                f'按 {claim["unit"]} 换算后 ROUND_HALF_UP 展示 {places} 位：{expected}',
                '只核查结构化字段；原始文字未自动解析，需人工确认字段忠实于原文'])
            if claim['direction'] != direction:
                result['errors'].append('方向错误')
            if value != expected:
                other = [u for u, scale in UNITS.items() if u != claim['unit'] and
                         (amount / scale).quantize(quantum, rounding=ROUND_HALF_UP) == value]
                result['errors'].append('数值或单位错误' if other else '数值错误')
                if other:
                    result['process'].append('数值与其他单位的展示值相同：' + '、'.join(other) + '；不能确定作者意图')
            result['expected'] = dict(value=str(expected), unit=claim['unit'], direction=direction,
                                      base_yuan=str(base), current_yuan=str(current), change_yuan=str(change))
    except (KeyError, ValueError, InvalidOperation, StopIteration, TypeError):
        return unknown('事实缺失、来源未通过验证或金额不可用')
    result['sources'] = sources
    result['status'] = '发现错误' if result['errors'] else '一致'
    if result['errors']:
        amount_text = f'本期金额为 {expected} {claim["unit"]}' if claim['value_kind'] == 'current' else f'同比{direction} {expected} {claim["unit"]}'
        result['correction'] = f'{claim["company"]}{claim["period"]}年{fact["name"]}：{amount_text}；较{claim["base_period"]}年{direction}。'
    return result


def render(result):
    lines = ['# 单条研报陈述核查', '',
             '纯模拟软件演示，不是真实财务结果。' if result['simulation'] else
             '本地提供年报的文件、页码与数值核验；未独立联网认证来源，不证明经营因果。',
             '', '结论：' + result['status'], '', '原文：' + str(result['claim'].get('original_text', '') if isinstance(result['claim'], dict) else result['claim']), '',
             '错误：' + '、'.join(result['errors']), '', '建议：' + str(result['correction'] or '无'), '', '核验过程：']
    lines.extend('- ' + p for p in result['process'])
    lines.extend(['', '来源：'])
    for e in result['sources']:
        lines.append(f'- {e["evidence_id"]} | {e["source_file"]} | 印刷页 {e["printed_page"]} / PDF页 {e["pdf_page"]} | {e["text"]}')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--stage2-run', type=Path)
    mode.add_argument('--simulated-demo', action='store_true')
    parser.add_argument('--claim', type=Path)
    parser.add_argument('--output', type=Path, default=Path('outputs/report_check'))
    args = parser.parse_args(argv)
    if args.stage2_run and not args.claim:
        parser.error('--stage2-run requires --claim')
    audit = {}
    if args.simulated_demo:
        fixture = json.loads((Path(__file__).resolve().parents[1] / 'examples/report_check/simulated.json').read_text(encoding='utf-8'))
        payload, claim = fixture['payload'], fixture['claim']
    else:
        claim = json.loads(args.claim.read_text(encoding='utf-8-sig'))
        try:
            from .final_release import load_agent_payload
            payload, audit = load_agent_payload(args.stage2_run)
        except (OSError, ValueError, KeyError, ImportError) as exc:
            result = dict(status='无法核实', simulation=False, llm_called=False, claim=claim,
                          errors=[], process=['来源加载失败：' + type(exc).__name__], sources=[], correction=None)
            payload = None
    if payload is not None:
        if args.simulated_demo and args.claim:
            claim = json.loads(args.claim.read_text(encoding='utf-8-sig'))
        result = check_claim(claim, payload, simulation=args.simulated_demo)
    result['source_audit'] = audit
    out = args.output / uuid.uuid4().hex
    out.mkdir(parents=True, exist_ok=False)
    (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'report.md').write_text(render(result), encoding='utf-8')
    print(json.dumps(dict(status=result['status'], errors=result['errors'], simulation=result['simulation'], output=str(out.resolve())), ensure_ascii=False))
    return 2 if result['status'] == '无法核实' else 0


if __name__ == '__main__':
    raise SystemExit(main())
