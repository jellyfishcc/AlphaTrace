"""Small DashScope chat adapter; no network activity during configuration."""
import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


def user_environment(name):
    if os.name != 'nt':
        return ''
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as registry:
            value, _ = winreg.QueryValueEx(registry, name)
            return value if isinstance(value,str) else ''
    except OSError:
        return ''


def setting(name):
    value=os.environ.get(name,'').strip()
    if value: return value,'process'
    value=user_environment(name).strip()
    return value,'windows_user' if value else 'missing'


@dataclass
class Config:
    key: str = field(repr=False)
    base_url: str
    model: str
    sources: dict

    @property
    def endpoint(self):
        parsed=urlsplit(self.base_url)
        if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path.rstrip('/')!='/compatible-mode/v1'):
            raise ValueError('DASHSCOPE_BASE_URL必须为无凭证和查询参数的HTTPS兼容接口地址')
        return self.base_url.rstrip('/')+'/chat/completions'


def configuration(model=None):
    key,ks=setting('DASHSCOPE_API_KEY')
    base,bs=setting('DASHSCOPE_BASE_URL')
    configured,ms=setting('DASHSCOPE_MODEL')
    if not configured: configured,ms=setting('TRACELAB_MODEL')
    return Config(key,base,model or configured or 'qwen-plus',
                  {'key':ks,'base_url':bs,'model':'argument' if model else ms if configured else 'default'})


def chat_body(model, prompt, content, max_tokens, schema=None):
    body=dict(model=model,messages=[{'role':'system','content':prompt}, {'role':'user','content':content}],
              max_tokens=max_tokens,stream=False,enable_thinking=False)
    if schema is not None:
        body['messages'][0]['content'] += '\n请返回JSON对象，遵循以下结构（由本地再次校验）：\n'+json.dumps(schema,ensure_ascii=False,separators=(',',':'))
        body['response_format']={'type':'json_object'}
    return body


def as_response(raw):
    """Normalize final chat content into the existing response/logging path."""
    if not isinstance(raw,dict): raise ValueError('无效响应对象')
    choices=raw.get('choices') or []
    if not isinstance(choices,list) or len(choices)!=1 or not isinstance(choices[0],dict):
        raise ValueError('预期单个模型返回')
    choice=choices[0]
    message=choice.get('message') or {}
    if not isinstance(message,dict): raise ValueError('无效消息对象')
    content=[]
    if message.get('refusal'):
        content.append({'type':'refusal','refusal':message['refusal']})
    if isinstance(message.get('content'),str):
        content.append({'type':'output_text','text':message['content']})
    complete=choice.get('finish_reason')=='stop'
    # Do not copy reasoning_content or arbitrary server fields.
    reason=choice.get('finish_reason')
    reason=reason if reason in ('stop','length','content_filter','tool_calls','function_call') else 'unknown'
    return dict(id=raw.get('id'),model=raw.get('model'),usage=raw.get('usage'),finish_reason=reason,
                status='completed' if complete else 'incomplete',
                incomplete_details=None if complete else {'reason':reason},
                output=[{'type':'message','role':'assistant','content':content}])
