"""One local adapter path, no network inference or CLI account changes."""
import asyncio
import json
from unittest.mock import patch
from sceneops_design_ai import AiRequest, AiSuggestion
from sceneops_design_ai.codebuddy import suggest

async def main():
    calls = []
    value = AiSuggestion(title='钥匙开门', goal='找到钥匙后打开家门', playerValue='得到明确进度反馈',
        given='玩家已取得钥匙', when='玩家与门交互', then='家门开启')
    async def local_cli(arguments, **kwargs):
        calls.append((arguments, kwargs))
        if arguments == ['--help']:
            return 'Currently supported: (hy3, glm-5.3)'
        return json.dumps({'subtype':'success','is_error':False,'structured_output':value.model_dump()})
    with patch('sceneops_design_ai.codebuddy.shutil.which', return_value='/local/codebuddy'), patch('sceneops_design_ai.codebuddy.invoke_cli', side_effect=local_cli):
        result = await suggest(AiRequest(model='glm-5.3', brief='钥匙与家门', current=value))
    arguments, _ = calls[1]
    assert arguments[arguments.index('--model') + 1] == 'glm-5.3'
    assert arguments[arguments.index('--tools') + 1] == ''
    assert result.suggestion == value and result.model == 'glm-5.3'
    print('PASS: selected model -> CodeBuddy arguments -> validated structured suggestion (mock CLI transport; no live AI request).')

asyncio.run(main())
