"""Small, task-oriented taxonomy; tools, evidence, and ownership remain independent."""
from .experience_models import ExperienceTopic

TOPICS = (
    ExperienceTopic(id="build_delivery", label="构建与交付", description="导出、编译、签名、安装与交付验证。"),
    ExperienceTopic(id="motion_interaction", label="体感与交互", description="陀螺仪、方向、计步、输入映射与交互反馈。"),
    ExperienceTopic(id="scene_animation", label="场景与动画", description="场景层级、镜头、坐标、动画与画面检查。"),
    ExperienceTopic(id="asset_performance", label="资产与性能", description="模型、纹理、压缩、加载与设备性能。"),
    ExperienceTopic(id="runtime_lifecycle", label="运行与播放", description="媒体播放、状态切换、初始化与销毁。"),
    ExperienceTopic(id="engineering_workflow", label="工程与协作", description="源码、生成器、版本、验证方法与协作边界。"),
)


def topic_text(ids):
    selected = set(ids)
    return ' '.join(topic.label for topic in TOPICS if topic.id in selected)
