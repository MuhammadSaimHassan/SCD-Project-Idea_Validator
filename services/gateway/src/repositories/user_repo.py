"""User and profile repository for M2."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.gateway.src.db.models import ProfileRow, UserRow
from shared.schemas import ComputeTier, GoalType, StudentProfile


class UserRepository:
    """Persistence operations for users and versioned student profiles."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_email(self, email: str) -> UserRow | None:
        stmt = select(UserRow).where(UserRow.email == email.lower())
        return self._session.scalar(stmt)

    def get_by_id(self, user_id: str) -> UserRow | None:
        return self._session.get(UserRow, user_id)

    def create_user(self, user_id: str, email: str, password_hash: str) -> UserRow:
        row = UserRow(id=user_id, email=email.lower(), password_hash=password_hash)
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def get_profile(self, user_id: str) -> StudentProfile | None:
        row = self._session.get(ProfileRow, user_id)
        if row is None:
            return None
        return StudentProfile(
            user_id=row.user_id,
            skills=json.loads(row.skills_json),
            hours_per_week=row.hours_per_week,
            weeks_available=row.weeks_available,
            team_size=row.team_size,
            compute=ComputeTier(row.compute),
            goal=GoalType(row.goal),
            interests=json.loads(row.interests_json),
            profile_version=row.profile_version,
        )

    def upsert_profile(self, profile: StudentProfile) -> StudentProfile:
        """Create or update profile, bumping profile_version on each update."""
        row = self._session.get(ProfileRow, profile.user_id)
        if row is None:
            row = ProfileRow(
                user_id=profile.user_id,
                skills_json=json.dumps(profile.skills),
                hours_per_week=profile.hours_per_week,
                weeks_available=profile.weeks_available,
                team_size=profile.team_size,
                compute=profile.compute.value,
                goal=profile.goal.value,
                interests_json=json.dumps(profile.interests),
                profile_version=1,
            )
            self._session.add(row)
        else:
            row.skills_json = json.dumps(profile.skills)
            row.hours_per_week = profile.hours_per_week
            row.weeks_available = profile.weeks_available
            row.team_size = profile.team_size
            row.compute = profile.compute.value
            row.goal = profile.goal.value
            row.interests_json = json.dumps(profile.interests)
            row.profile_version += 1

        self._session.commit()
        self._session.refresh(row)
        updated = self.get_profile(row.user_id)
        if updated is None:
            raise RuntimeError("Failed to reload saved profile")
        return updated
