import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")
    created_versions = relationship("DatasetVersion", back_populates="creator")
    assigned_issues = relationship("Issue", back_populates="assignee")
    comments = relationship("Comment", back_populates="author")
    approvals = relationship("Approval", back_populates="reviewer")


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    memberships = relationship("Membership", back_populates="workspace", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="workspace", cascade="all, delete-orphan")
    rules = relationship("Rule", back_populates="workspace", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="workspace", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    # role: admin | steward | stakeholder | contributor
    role = Column(String(50), default="contributor", nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", name="uq_membership_user_workspace"),
    )

    # Relationships
    user = relationship("User", back_populates="memberships")
    workspace = relationship("Workspace", back_populates="memberships")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="projects")
    datasets = relationship("Dataset", back_populates="project", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan")


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)  # csv | xlsx
    raw_file_path = Column(String(500), nullable=False)
    status = Column(String(50), default="processing", nullable=False)  # processing | ready | failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="datasets")
    versions = relationship("DatasetVersion", back_populates="dataset", cascade="all, delete-orphan")
    columns = relationship("ColumnModel", back_populates="dataset", cascade="all, delete-orphan")
    rows = relationship("RowModel", back_populates="dataset", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="dataset", cascade="all, delete-orphan")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version"),
    )

    # Relationships
    dataset = relationship("Dataset", back_populates="versions")
    creator = relationship("User", back_populates="created_versions")
    cell_values = relationship("CellValue", back_populates="dataset_version", cascade="all, delete-orphan")
    changes = relationship("Change", back_populates="dataset_version", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="dataset_version")


class ColumnModel(Base):
    __tablename__ = "columns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    position = Column(Integer, default=0, nullable=False)
    inferred_type = Column(String(50), nullable=True)  # string | integer | float | date | boolean
    semantic_hint = Column(String(100), nullable=True)  # currency, state, email, etc.
    stats_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    dataset = relationship("Dataset", back_populates="columns")
    cell_values = relationship("CellValue", back_populates="column", cascade="all, delete-orphan")
    changes = relationship("Change", back_populates="column", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="column")


class RowModel(Base):
    __tablename__ = "rows"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    row_index = Column(Integer, nullable=False, index=True)
    # RAW JSON IS IMMUTABLE
    raw_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("dataset_id", "row_index", name="uq_dataset_row_index"),
    )

    # Relationships
    dataset = relationship("Dataset", back_populates="rows")
    cell_values = relationship("CellValue", back_populates="row", cascade="all, delete-orphan")
    changes = relationship("Change", back_populates="row", cascade="all, delete-orphan")


class CellValue(Base):
    __tablename__ = "cell_values"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_version_id = Column(String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    row_id = Column(String(36), ForeignKey("rows.id", ondelete="CASCADE"), nullable=False, index=True)
    column_id = Column(String(36), ForeignKey("columns.id", ondelete="CASCADE"), nullable=False, index=True)
    value = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("dataset_version_id", "row_id", "column_id", name="uq_cell_version_row_col"),
    )

    # Relationships
    dataset_version = relationship("DatasetVersion", back_populates="cell_values")
    row = relationship("RowModel", back_populates="cell_values")
    column = relationship("ColumnModel", back_populates="cell_values")


class Rule(Base):
    __tablename__ = "rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    column_pattern = Column(String(255), nullable=True)
    transform_type = Column(String(100), nullable=False)  # trim, case, parse_date, etc.
    config_json = Column(JSON, nullable=False, default=dict)
    scope = Column(String(50), default="project", nullable=False)  # workspace | project
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="rules")
    changes = relationship("Change", back_populates="rule")


class Change(Base):
    __tablename__ = "changes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_version_id = Column(String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    row_id = Column(String(36), ForeignKey("rows.id", ondelete="CASCADE"), nullable=False, index=True)
    column_id = Column(String(36), ForeignKey("columns.id", ondelete="CASCADE"), nullable=False, index=True)
    before = Column(Text, nullable=True)
    after = Column(Text, nullable=True)
    source = Column(String(20), nullable=False)  # rule | ai | human
    rule_id = Column(String(36), ForeignKey("rules.id", ondelete="SET NULL"), nullable=True)
    confidence = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending | accepted | rejected | reverted
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    dataset_version = relationship("DatasetVersion", back_populates="changes")
    row = relationship("RowModel", back_populates="changes")
    column = relationship("ColumnModel", back_populates="changes")
    rule = relationship("Rule", back_populates="changes")


class Issue(Base):
    __tablename__ = "issues"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(100), nullable=False)  # missing_value, duplicate, mixed_format, etc.
    severity = Column(String(20), nullable=False)  # low | medium | high | critical
    column_id = Column(String(36), ForeignKey("columns.id", ondelete="CASCADE"), nullable=True, index=True)
    row_ids = Column(JSON, nullable=True)  # List of impacted row ids or row indices
    status = Column(String(20), default="open", nullable=False)  # open | in_review | resolved | dismissed
    assignee_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    dataset = relationship("Dataset", back_populates="issues")
    column = relationship("ColumnModel", back_populates="issues")
    assignee = relationship("User", back_populates="assigned_issues")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_version_id = Column(String(36), ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    status = Column(String(20), default="draft", nullable=False)  # draft | in_review | approved | published
    layout_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="reports")
    dataset_version = relationship("DatasetVersion", back_populates="reports")
    approvals = relationship("Approval", back_populates="report", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    target_type = Column(String(30), nullable=False)  # cell | issue | report | report_block
    target_id = Column(String(255), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    parent_id = Column(String(36), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    resolved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    author = relationship("User", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], back_populates="replies")
    replies = relationship("Comment", back_populates="parent", cascade="all, delete-orphan")


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    report_id = Column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    decision = Column(String(20), nullable=False)  # approved | change_requested | rejected
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    report = relationship("Report", back_populates="approvals")
    reviewer = relationship("User", back_populates="approvals")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="audit_logs")
