"""Explicit Qwen-adapter replay demo; never enables real API execution."""
import argparse
import json
import uuid
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from .final_release import load_agent_payload
from .stage3_input import read
from .stage3 import write
from .agent import investigate
from .qwen_decider import QwenDecider,ReplayTransport,ExportScope


def main(argv=None):
    parser=argparse.ArgumentParser(description='仅使用假响应验证Qwen决策适配器，不允许真实请求')
    parser.add_argument('--stage2-run',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('outputs/agent_replay'))
    args=parser.parse_args(argv)
    with patch('socket.socket',side_effect=RuntimeError('offline_network_blocked')), \
         patch('tracelab.bailian.configuration',side_effect=RuntimeError('offline_credentials_blocked')), \
         patch('tracelab.stage3.call_api',side_effect=RuntimeError('offline_api_blocked')):
        payload,audit=load_agent_payload(args.stage2_run)
        scope=ExportScope(frozenset({'net_profit','operating_cashflow'}),
            frozenset({'E18','E07_28','E07_29','F_net_profit','F_operating_cashflow'}),'offline_demo_not_external_authorization')
        evidence=next(e for e in payload['evidence'] if e['evidence_id']=='E18')
        analysis={'claims':[{'kind':'hypothesis','statement':'待验证：经营收支变化是否足以解释走势分化',
            'metric_ids':['operating_cashflow'],'citations':[{'evidence_id':'E18','quote':evidence['text'][:200]}],
            'amounts':[],'support_limit':'仅完成工具与引用流程演示，未形成经营因果结论',
            'accounting_links':[],'comparison_basis':'none'}],'questions':['还有哪些经营因素需要原文支持？']}
        actions=[{'action':'fact_get','arguments':{'fact_id':'operating_cashflow'}},
                 {'action':'search','arguments':{'metric_id':'operating_cashflow'}},
                 {'action':'get','arguments':{'evidence_id':'E18'}},
                 {'action':'explain','arguments':{'analysis':analysis}}]
        # Simulated usage is deliberately absent: estimate-only replay would stop after one request.
        # Supply explicitly synthetic usage to exercise multi-turn accounting, never report as real usage.
        responses=[{'model':'qwen-plus','choices':[{'finish_reason':'stop','message':{'content':json.dumps(a,ensure_ascii=False)}}],
                    'usage':{'prompt_tokens':100,'completion_tokens':50}} for a in actions]
        decider=QwenDecider(payload,scope,ReplayTransport(responses))
        run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:10]
        out=args.output/run_id
        result=investigate(payload,read(args.stage2_run/'investigation_plan.json'),decider,out)
        write(out/'source_audit.json',audit)
        write(out/'replay_notice.json',{'simulation':True,'all_responses_and_usage_are_synthetic':True,
              'external_authorization':False,'actions':actions,'note':'预设协议测试，不证明自主决策或经营因果'})
        print(json.dumps({'output':str(out.resolve()),'status':result['status'],'simulation':True,'llm_called':False},ensure_ascii=False))
        return 1 if result['status']=='validation_failed' else 0


if __name__=='__main__':raise SystemExit(main())
