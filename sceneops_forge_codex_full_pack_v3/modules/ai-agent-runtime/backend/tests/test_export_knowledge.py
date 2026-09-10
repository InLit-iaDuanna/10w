"""Product knowledge routing and real provider-bound instruction assembly."""
import unittest
from importlib.resources import files

from sceneops_ai_agents.export_knowledge import (
    SKILLS, load_export_knowledge, native_export_skill_catalog,
)
from test_export_agent import Provider, task
from sceneops_ai_agents.export_agent import ExportAgent


class ExportKnowledgeTests(unittest.TestCase):
    def test_platform_selection_does_not_load_unrelated_publishing(self):
        android = load_export_knowledge(['android'])
        self.assertEqual(android.loaded_skills,
            ('sceneops-export-environment', 'sceneops-export-android'))
        desktop = load_export_knowledge(['mac-arm64', 'mac-x64', 'win-x64'])
        self.assertEqual(desktop.loaded_skills,
            ('sceneops-export-environment', 'sceneops-export-desktop'))
        publication = load_export_knowledge(['android'], native=True, publish=True)
        self.assertIn('sceneops-release-publish', publication.loaded_skills)
        with self.assertRaises(ValueError):
            load_export_knowledge(['../../anything'])

    def test_actual_provider_receives_selected_resource_content_and_audit(self):
        provider = Provider()
        result = ExportAgent(provider)(task(), '分析失败原因')
        instructions = provider.calls[0][1]['instructions']
        expected = load_export_knowledge(['android'])
        self.assertEqual(instructions, expected.instructions)
        self.assertEqual(result['invocation']['loaded_skills'], list(expected.loaded_skills))
        self.assertNotIn('sceneops-release-publish', result['invocation']['loaded_skills'])

    def test_native_catalog_references_packaged_readable_resources(self):
        root = files('sceneops_ai_agents')
        catalog = native_export_skill_catalog()
        for name, _ in SKILLS:
            path = root.joinpath(f'skills/{name}/SKILL.md')
            self.assertIn(str(path), catalog)
            self.assertTrue(path.read_text(encoding='utf-8').strip())
            self.assertTrue(root.joinpath(f'skills/{name}/references/sources.md').is_file())


if __name__ == '__main__':
    unittest.main()
