"""Per-investigation CNY reservations. Not a provider billing guarantee."""
from decimal import Decimal
from datetime import datetime, timezone, timedelta

PRICE_URL = 'https://help.aliyun.com/zh/model-studio/qwen-plus'
# Rechecked 2026-11-13 (Asia/Shanghai): qwen-plus, cn-beijing,
# functionally equivalent to qwen-plus-2025-12-01; ordinary real-time pricing,
# enable_thinking=False, stream=False; no Batch or explicit cache creation.
# Input/output CNY per million: <=128k 0.8/2; <=256k 2.4/20; <=1m 4.8/48.
# Audit: docs/dev-reports/2026-11-13-price-date-maintenance.md
VERIFIED_DATE = '2026-11-13'
ENDPOINT = 'https://ws-6sp1nti4y4d07vun.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions'
# Official model ceiling, NOT an estimate from bytes. Too large for this run's
# 60000-token hard limit. Free-tier mode uses it only for auxiliary CNY reservations.
MODEL_INPUT_CEILING = 997952


def price(a, b):
    i,o = ('0.8','2') if a<=128000 else ('2.4','20') if a<=256000 else ('4.8','48')
    return (Decimal(a)*Decimal(i)+Decimal(b)*Decimal(o))/Decimal(1000000)


class CostLedger:
    def __init__(self, limit='30.00', *, token_mode='strict_bound'):
        if token_mode not in ('strict_bound','usage_target'):raise ValueError('invalid_token_mode')
        self.token_mode=token_mode
        self.limit=Decimal(limit)
        if not self.limit.is_finite() or not 0<self.limit<=30: raise ValueError('invalid_cost_limit')
        self.rows=[]; self.unknown=False

    def snapshot(self):
        return dict(limit_cny=str(self.limit),reserved_cny=str(sum((Decimal(r['reserved_cny']) for r in self.rows),Decimal(0))),
                    accounted_cny=str(sum((Decimal(r['accounted_cny']) for r in self.rows),Decimal(0))),
                    status='unknown' if self.unknown else 'usage_priced_not_invoice',requests=self.rows.copy(),
                    price_source=PRICE_URL,price_verified_date=VERIFIED_DATE,token_mode=self.token_mode,
                    token_target=60000,pre_request_token_bound_available=self.token_mode=='strict_bound')

    def reserve(self, a, b):
        if self.unknown: raise ValueError('cost_unknown_stop')
        if type(a)!=int or type(b)!=int or not 0<=a<=MODEL_INPUT_CEILING or not 0<=b<=1200:
            raise ValueError('invalid_token_bound')
        if len(self.rows)>=5: raise ValueError('request_budget_exhausted')
        used=sum((Decimal(r['accounted_cny']) for r in self.rows),Decimal(0))
        estimate=price(a,b)
        if used>=self.limit or used+estimate>self.limit: raise ValueError('cost_budget_exhausted')
        used_tokens=sum(r['token_charge'] for r in self.rows)
        if (used_tokens+a+b>60000 if self.token_mode=='strict_bound' else used_tokens>=60000):
            raise ValueError('token_budget_exhausted')
        row=dict(input_bound=a,output_bound=b,reserved_cny=str(estimate),accounted_cny=str(estimate),
                 token_charge=a+b,status='reserved',request_id=None)
        self.rows.append(row)
        return row

    def settle(self,row,raw,request_id):
        row['request_id']=request_id
        usage=raw.get('usage') or {}; a=usage.get('prompt_tokens'); b=usage.get('completion_tokens')
        if type(a)!=int or type(b)!=int or a<0 or b<0:
            self.fail(row); raise ValueError('cost_usage_unknown')
        row.update(input_tokens=a,output_tokens=b)
        if a>row['input_bound'] or b>row['output_bound']:
            self.fail(row); raise ValueError('token_bound_violated')
        # Ignore cache discounts: conservative list-price accounting, not invoice.
        row.update(accounted_cny=str(price(a,b)),token_charge=a+b,status='usage_priced_not_invoice')

    def fail(self,row):
        row['status']='unknown';self.unknown=True


def guarded_send(ledger, body, send, input_bound):
    row=ledger.reserve(input_bound,body['max_tokens'])
    try:
        raw,rid=send()
        ledger.settle(row,raw,rid)
        return raw,rid
    except Exception:
        if row['status']=='reserved': ledger.fail(row)
        raise


def check_live_price(body, endpoint):
    if endpoint!=ENDPOINT or body.get('model')!='qwen-plus': raise ValueError('cost_model_endpoint_mismatch')
    today=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    if today!=VERIFIED_DATE: raise ValueError('price_reverification_required')
    if body.get('enable_thinking') is not False or body.get('stream') is not False:
        raise ValueError('unsupported_billing_mode')
    if set(body)-{'model','messages','max_tokens','stream','enable_thinking','response_format'}:
        raise ValueError('unsupported_billable_feature')


FREE_TIER = dict(model='qwen-plus',region='cn-beijing',total_tokens=1000000,
                 remaining_tokens_at_confirmation=958750,expires='2027-01-15',
                 free_tier_only=True,confirmation_source='user_console_confirmation_2026-11-02',
                 api_verified=False,workspace_id='ws-6sp1nti4y4d07vun',workspace_match_user_confirmed=True)


def check_free_tier_confirmation(workspace_confirmed):
    if workspace_confirmed is not True:raise ValueError('free_tier_workspace_unconfirmed')
    if datetime.now(timezone(timedelta(hours=8))).date().isoformat()>=FREE_TIER['expires']:
        raise ValueError('free_tier_confirmation_expired')
