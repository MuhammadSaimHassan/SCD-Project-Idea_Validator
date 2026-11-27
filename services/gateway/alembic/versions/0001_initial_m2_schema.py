"""Initial M2 schema: users, profiles, ideas, verdicts, approvals, traces, runs.

Revision ID: 0001_initial_m2
Revises:
Create Date: 2026-11-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_m2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "profiles",
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("skills_json", sa.Text(), nullable=False),
        sa.Column("hours_per_week", sa.Float(), nullable=False),
        sa.Column("weeks_available", sa.Float(), nullable=False),
        sa.Column("team_size", sa.Integer(), nullable=False),
        sa.Column("compute", sa.String(length=32), nullable=False),
        sa.Column("goal", sa.String(length=32), nullable=False),
        sa.Column("interests_json", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "ideas",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ideas_user_id", "ideas", ["user_id"], unique=False)

    op.create_table(
        "idea_versions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "idea_id",
            sa.String(length=64),
            sa.ForeignKey("ideas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_idea_versions_idea_id", "idea_versions", ["idea_id"], unique=False)

    op.create_table(
        "verdicts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "version_id",
            sa.String(length=64),
            sa.ForeignKey("idea_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verdicts_version_id", "verdicts", ["version_id"], unique=False)
    op.create_index("ix_verdicts_run_id", "verdicts", ["run_id"], unique=False)

    op.create_table(
        "dimension_scores",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "verdict_id",
            sa.String(length=64),
            sa.ForeignKey("verdicts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_dimension_scores_verdict_id", "dimension_scores", ["verdict_id"], unique=False
    )

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_approvals_run_id", "approvals", ["run_id"], unique=False)

    op.create_table(
        "traces_index",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "idea_id",
            sa.String(length=64),
            sa.ForeignKey("ideas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turns_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_idea_id", "conversations", ["idea_id"], unique=False)

    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("events_json", sa.Text(), nullable=False),
        sa.Column("pending_question_json", sa.Text(), nullable=True),
        sa.Column("pending_approval_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runs_user_id", "runs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("runs")
    op.drop_table("conversations")
    op.drop_table("traces_index")
    op.drop_table("approvals")
    op.drop_table("dimension_scores")
    op.drop_table("verdicts")
    op.drop_table("idea_versions")
    op.drop_table("ideas")
    op.drop_table("profiles")
    op.drop_table("users")
