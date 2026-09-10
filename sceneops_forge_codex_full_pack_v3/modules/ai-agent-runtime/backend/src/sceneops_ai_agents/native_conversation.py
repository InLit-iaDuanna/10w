"""Project native CLI events into the conversation, without parsing model prose."""
def append_activity(task, event):
    task.observations['codex_activity'] = event
    items = task.observations.setdefault('native_conversation', [])
    for tool in event.get('tools', []):
        item = next((item for item in items if item['type'] == 'tool' and item.get('id') == tool.get('id')), None)
        if item is None:
            item = {'type': 'tool', 'id': tool.get('id'), 'state': 'running'}
            items.append(item)
        item.update(name=tool.get('name', '工具'), input=tool.get('input', {}))
    kind = event.get('type')
    if kind == 'message_start':
        key = event.get('id') or str(len(items))
        task.observations['native_message_id'] = key
        items.append({'type': 'assistant', 'id': key, 'text': '', 'complete': False})
    elif kind in ('text_delta', 'message_completed'):
        key = event.get('id') or task.observations.get('native_message_id')
        message = next((item for item in items if item['type'] == 'assistant' and item.get('id') == key), None)
        if message is None:
            message = {'type': 'assistant', 'id': key, 'text': '', 'complete': False}
            items.append(message)
        if kind == 'text_delta':
            message['text'] += event.get('text', '')
        else:
            message.update(text=event.get('text', ''), complete=True)
    elif kind == 'tool_start':
        items.append({'type': 'tool', 'id': event.get('id'), 'name': event.get('name', '工具'), 'state': 'running'})
    elif kind == 'tool_completed':
        for result in event.get('results', []):
            for item in items:
                if item['type'] == 'tool' and item.get('id') == result.get('id'):
                    item['state'] = 'failed' if result.get('failed') else 'completed'
    elif kind == 'assistant_message':
        items.append({'type': 'assistant', 'text': event.get('text', ''), 'complete': True})
    elif kind in ('command_execution', 'file_change', 'mcp_tool_call'):
        key = event.get('item_id')
        item = next((item for item in items if key and item.get('id') == key), None)
        if item is None:
            item = {'type': 'tool', 'id': key, 'name': {'command_execution': '运行命令', 'file_change': '修改文件', 'mcp_tool_call': '调用工具'}[kind]}
            items.append(item)
        if isinstance(event.get('input'), dict):
            item['input'] = event['input']
        if event.get('files'):
            item['input'] = {'path': ', '.join(file['path'] for file in event['files'] if isinstance(file.get('path'), str))}
        item['state'] = event.get('status', 'running' if event.get('phase') == 'started' else 'completed')
