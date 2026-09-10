"""Return registered browser pixels through MCP, without granting filesystem access."""
import base64


def browser_image_content(service, task, evidence):
    run = evidence.get('run', {})
    observation = run.get('observation') or {}
    artifact = observation.get('screenshot_artifact')
    metadata = {'status': 'no_current_screenshot', 'visual_reviewed': False}
    evidence['model_image_input'] = metadata
    if not task.authorization_card.allow_model_image_input or not task.grant.allow_model_image_input:
        metadata['status'] = 'not_authorized'
        return []
    if run.get('status') != 'succeeded' or run.get('source_stale') or not artifact:
        return []
    service.check_grant(task.id)
    path = service.production.model_image_path(task, artifact['id'], artifact['version'], run['id'])
    metadata.update(status='attached', artifact_id=artifact['id'], version=artifact['version'],
                    browser_run_id=run['id'],
                    notice='截图像素已随本次工具结果附上。请直接查看图片；附件存在不代表视觉或玩法验证通过。')
    return [{'type': 'image', 'mimeType': 'image/png',
             'data': base64.b64encode(path.read_bytes()).decode('ascii')}]
