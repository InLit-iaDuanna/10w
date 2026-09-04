"""Deterministic, ChangeSet-anchored patch-note generation and editing."""

from __future__ import annotations

from typing import Dict, List

from .enums import PatchNoteStatus
from .errors import PolicyError
from .models_common import ApprovedChangeSet
from .models_release import (
    PatchNote,
    PatchNoteEdit,
    PatchNoteEntry,
    ReleaseCandidate,
    patch_note_content_checksum,
)
from .ports import Clock
from .repository import InMemoryReleaseRepository
from .requests import EditPatchNoteRequest, GeneratePatchNoteRequest


class PatchNoteService:
    def __init__(
        self, repository: InMemoryReleaseRepository, clock: Clock
    ) -> None:
        self.repository = repository
        self.clock = clock

    def generate(self, request: GeneratePatchNoteRequest) -> PatchNote:
        candidate = self.repository.get_candidate(request.candidate_id)
        changes = {item.change_set_id: item for item in request.change_sets}
        if len(changes) != len(request.change_sets):
            raise PolicyError(
                "DUPLICATE_CHANGE_SET",
                "Patch-note ChangeSets must be unique.",
                details={"candidate_id": candidate.candidate_id},
            )
        if set(changes) != set(candidate.approved_change_set_ids):
            raise PolicyError(
                "CHANGE_SET_SCOPE_MISMATCH",
                "Patch notes must use exactly the ChangeSets shipped by the candidate.",
                details={"candidate_id": candidate.candidate_id},
            )
        entries = [self._entry(candidate, changes[key]) for key in sorted(changes)]
        now = self.clock.now()
        title = self._safe_text(request.title)
        content_checksum = patch_note_content_checksum(title, entries, None)
        note = PatchNote(
            patch_note_id=request.patch_note_id,
            candidate_id=candidate.candidate_id,
            project_id=candidate.project_id,
            game_id=candidate.game_id,
            title=title,
            entries=entries,
            original_entries=entries,
            revision=1,
            original_content_checksum=content_checksum,
            content_checksum=content_checksum,
            status=PatchNoteStatus.DRAFT,
            edits=[],
            created_at=now,
            updated_at=now,
        )
        self.repository.add_patch_note(note)
        return note

    def edit(self, request: EditPatchNoteRequest) -> PatchNote:
        note = self.repository.get_patch_note(request.patch_note_id)
        originals = {entry.change_set_id: entry for entry in note.entries}
        requested_ids = [entry.change_set_id for entry in request.entries]
        if (
            len(requested_ids) != len(set(requested_ids))
            or not set(requested_ids).issubset(originals)
        ):
            raise PolicyError(
                "UNSOURCED_PATCH_NOTE_ENTRY",
                "Human edits may reorder, reword, or remove entries but cannot add claims.",
                details={"patch_note_id": note.patch_note_id},
            )
        edited_entries = [self._edited_entry(entry, originals) for entry in request.entries]
        now = self.clock.now()
        revision = note.revision + 1
        editorial_note = (
            self._safe_text(request.editorial_note)
            if request.editorial_note is not None
            else None
        )
        content_checksum = patch_note_content_checksum(
            note.title, edited_entries, editorial_note
        )
        edit = PatchNoteEdit(
            revision=revision,
            editor_id=request.editor_id,
            edited_at=now,
            title=note.title,
            entries=edited_entries,
            editorial_note=editorial_note,
            content_checksum=content_checksum,
        )
        updated = note.model_copy(
            update={
                "entries": edited_entries,
                "editorial_note": editorial_note,
                "revision": revision,
                "content_checksum": content_checksum,
                "edits": [*note.edits, edit],
                "status": PatchNoteStatus.DRAFT,
                "updated_at": now,
            }
        )
        updated = PatchNote.model_validate(updated.model_dump())
        self.repository.save_patch_note(updated)
        return updated

    def _entry(
        self, candidate: ReleaseCandidate, change: ApprovedChangeSet
    ) -> PatchNoteEntry:
        if (
            not change.approved
            or not change.approval_ids
            or change.approved_at is None
            or change.project_id != candidate.project_id
            or change.game_id != candidate.game_id
            or change.included_source_commit.lower() != candidate.source_commit.lower()
        ):
            raise PolicyError(
                "UNAPPROVED_OR_UNSHIPPED_CHANGE_SET",
                "Patch-note source is not an approved ChangeSet shipped in this candidate.",
                details={"change_set_id": change.change_set_id},
            )
        return PatchNoteEntry(
            change_set_id=change.change_set_id,
            title=self._safe_text(change.title),
            body=self._safe_text(change.summary),
            approval_ids=change.approval_ids,
            approved_at=change.approved_at,
        )

    def _edited_entry(
        self,
        entry: PatchNoteEntry,
        originals: Dict[str, PatchNoteEntry],
    ) -> PatchNoteEntry:
        original = originals[entry.change_set_id]
        if (
            entry.approval_ids != original.approval_ids
            or entry.approved_at != original.approved_at
        ):
            raise PolicyError(
                "PATCH_NOTE_PROVENANCE_CHANGED",
                "Patch-note edits cannot change ChangeSet approval provenance.",
                details={"change_set_id": entry.change_set_id},
            )
        return entry.model_copy(
            update={
                "title": self._safe_text(entry.title),
                "body": self._safe_text(entry.body),
            }
        )

    @staticmethod
    def _safe_text(value: str) -> str:
        if any(character in value for character in ("<", ">", "\x00")):
            raise PolicyError(
                "UNSAFE_PATCH_NOTE_TEXT",
                "Patch-note text cannot contain raw HTML or NUL bytes.",
                details={},
            )
        return value
