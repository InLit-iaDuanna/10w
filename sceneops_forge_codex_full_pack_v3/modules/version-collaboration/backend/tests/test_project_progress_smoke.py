"""Project progress preserves planning facts without claiming production completion."""
import unittest
from pydantic import ValidationError
from version_collaboration.tree_router import TreeProgress


class ProjectProgressSmoke(unittest.TestCase):
    def test_cards_and_versions_preserve_links_and_reject_incomplete_card(self):
        base = dict(stage='cards', confirmed_versions=1, planned_cards=1,
                    card_branches=1, milestones={}, branch_labels={})
        progress = TreeProgress(**base, cards=[dict(card_id='gameplay', title='战斗',
            description='制作射击循环', acceptance='可以击败目标', branches=['feature/gameplay'])],
            versions=[dict(number=1, title='项目方向', confirmed_at='2026-09-08T00:00:00Z')])
        self.assertEqual(progress.cards[0].branches, ('feature/gameplay',))
        self.assertIsNone(progress.versions[0].commit)
        self.assertEqual(TreeProgress(**base).cards, ())
        with self.assertRaises(ValidationError):
            TreeProgress(**base, cards=[dict(card_id='gameplay', title='战斗')])
