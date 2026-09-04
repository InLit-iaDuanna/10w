import unittest

from logic_studio.models import CompileTemplateRequest
from logic_studio.service import LogicStudioService
from logic_studio.tests.support import compile_example, load_json


class ServiceTests(unittest.TestCase):
    def test_generates_edit_play_and_behavior_tests(self):
        plan = LogicStudioService().generate_tests(
            compile_example("hero-key-door.binding.json")
        )
        self.assertEqual(
            {test.test_kind for test in plan.tests},
            {"edit_mode", "play_mode", "behavior"},
        )
        self.assertEqual(plan.mode.value, "live")

    def test_compile_endpoint_service_reports_planned_mode(self):
        payload = load_json("contracts/examples/warehouse-switch-door.binding.json")
        payload["mode"] = "planned"
        graph = LogicStudioService().compile_template(
            CompileTemplateRequest.model_validate(payload)
        )
        self.assertEqual(graph.mode.value, "planned")


if __name__ == "__main__":
    unittest.main()
