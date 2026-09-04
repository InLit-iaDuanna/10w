from __future__ import annotations

import unittest

from build_release.enums import PatchNoteStatus
from build_release.errors import PolicyError
from build_release.models_common import ApprovedChangeSet
from build_release.requests import EditPatchNoteRequest, GeneratePatchNoteRequest

from support import (
    create_patch_note,
    create_ready_candidate,
    make_build_pair,
    make_service,
    record_pair,
)


class PatchNoteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service, self.catalog, _, _ = make_service()
        self.pair = make_build_pair("notes")
        record_pair(self.service, self.catalog, self.pair)
        self.candidate = create_ready_candidate(
            self.service, self.pair, "candidate.notes"
        )

    def test_generation_uses_only_approved_shipped_change_sets(self) -> None:
        note = create_patch_note(
            self.service, self.pair, self.candidate, "patch-note.notes"
        )
        self.assertEqual(note.revision, 1)
        self.assertEqual(
            [entry.change_set_id for entry in note.entries],
            self.candidate.approved_change_set_ids,
        )
        self.assertTrue(note.entries[0].approval_ids)
        self.assertEqual(note.content_checksum, note.original_content_checksum)

    def test_unapproved_or_cross_project_change_is_rejected(self) -> None:
        original = self.pair.change_sets[0]
        unapproved = original.model_copy(update={"approved": False})
        with self.assertRaisesRegex(PolicyError, "not an approved ChangeSet"):
            self.service.generate_patch_note(
                GeneratePatchNoteRequest(
                    patch_note_id="patch-note.unapproved",
                    candidate_id=self.candidate.candidate_id,
                    title="发布说明",
                    change_sets=[unapproved],
                )
            )

        cross_project = original.model_copy(update={"project_id": "project.other"})
        with self.assertRaisesRegex(PolicyError, "not an approved ChangeSet"):
            self.service.generate_patch_note(
                GeneratePatchNoteRequest(
                    patch_note_id="patch-note.cross-project",
                    candidate_id=self.candidate.candidate_id,
                    title="发布说明",
                    change_sets=[cross_project],
                )
            )

    def test_human_edit_preserves_anchor_and_revision_history(self) -> None:
        note = create_patch_note(
            self.service, self.pair, self.candidate, "patch-note.edit"
        )
        entry = note.entries[0].model_copy(
            update={"title": "门锁交互修复", "body": "持有钥匙后可稳定开门。"}
        )
        edited = self.service.edit_patch_note(
            EditPatchNoteRequest(
                patch_note_id=note.patch_note_id,
                editor_id="user.release-editor",
                entries=[entry],
                editorial_note="人工精简措辞。",
            )
        )
        self.assertEqual(edited.revision, 2)
        self.assertEqual(edited.entries[0].change_set_id, note.entries[0].change_set_id)
        self.assertEqual(len(edited.edits), 1)
        self.assertEqual(edited.edits[0].entries, edited.entries)
        self.assertEqual(edited.edits[0].content_checksum, edited.content_checksum)
        self.assertEqual(edited.original_entries, note.entries)
        self.assertEqual(edited.status, PatchNoteStatus.DRAFT)

    def test_human_edit_cannot_add_unsourced_claim_or_raw_html(self) -> None:
        note = create_patch_note(
            self.service, self.pair, self.candidate, "patch-note.guard"
        )
        invented = note.entries[0].model_copy(
            update={"change_set_id": "changeset.invented.claim"}
        )
        with self.assertRaisesRegex(PolicyError, "cannot add claims"):
            self.service.edit_patch_note(
                EditPatchNoteRequest(
                    patch_note_id=note.patch_note_id,
                    editor_id="user.release-editor",
                    entries=[invented],
                )
            )

        unsafe = note.entries[0].model_copy(update={"body": "<script>bad</script>"})
        with self.assertRaisesRegex(PolicyError, "raw HTML"):
            self.service.edit_patch_note(
                EditPatchNoteRequest(
                    patch_note_id=note.patch_note_id,
                    editor_id="user.release-editor",
                    entries=[unsafe],
                )
            )


if __name__ == "__main__":
    unittest.main()
