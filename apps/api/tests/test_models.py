
from app.models.entities import (
    Approval,
    AuditLog,
    CellValue,
    Change,
    ColumnModel,
    Comment,
    Dataset,
    DatasetVersion,
    Issue,
    Membership,
    Project,
    Report,
    RowModel,
    Rule,
    User,
    Workspace,
)


def test_full_schema_creation_and_relationships(db_session):
    # 1. Create User
    user = User(email="steward@example.com", password_hash="hashed_pw", name="Data Steward")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.id is not None

    # 2. Create Workspace and Membership
    ws = Workspace(name="Acme Analytics")
    db_session.add(ws)
    db_session.commit()
    db_session.refresh(ws)

    member = Membership(user_id=user.id, workspace_id=ws.id, role="steward")
    db_session.add(member)
    db_session.commit()

    # 3. Create Project
    project = Project(workspace_id=ws.id, name="Sales Q3 Cleanup")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # 4. Create Dataset
    dataset = Dataset(
        project_id=project.id,
        name="sales_raw.csv",
        source_type="csv",
        raw_file_path="/uploads/sales_raw.csv",
    )
    db_session.add(dataset)
    db_session.commit()
    db_session.refresh(dataset)

    # 5. Create DatasetVersion
    version = DatasetVersion(
        dataset_id=dataset.id,
        version_number=1,
        created_by=user.id,
        note="Initial raw upload",
    )
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    # 6. Create Column & Row (Raw json immutable)
    col = ColumnModel(
        dataset_id=dataset.id,
        name="Amount",
        inferred_type="float",
        semantic_hint="currency",
        stats_json={"null_pct": 0.05, "distinct_count": 42},
    )
    db_session.add(col)

    row = RowModel(
        dataset_id=dataset.id,
        row_index=0,
        raw_json={"Amount": "$1,200.50", "Date": "2024-03-01"},
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(col)
    db_session.refresh(row)

    # 7. Create CellValue
    cell = CellValue(
        dataset_version_id=version.id,
        row_id=row.id,
        column_id=col.id,
        value="1200.50",
    )
    db_session.add(cell)

    # 8. Create Rule
    rule = Rule(
        workspace_id=ws.id,
        name="Currency cleaner",
        column_pattern=".*Amount.*",
        transform_type="parse_number/currency",
        config_json={"strip": ["$", ","]},
        scope="project",
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)

    # 9. Create Change
    change = Change(
        dataset_version_id=version.id,
        row_id=row.id,
        column_id=col.id,
        before="$1,200.50",
        after="1200.50",
        source="rule",
        rule_id=rule.id,
        confidence=1.0,
        reason="Stripped currency symbols and parsed as float",
        status="accepted",
    )
    db_session.add(change)

    # 10. Create Issue
    issue = Issue(
        dataset_id=dataset.id,
        type="mixed_format",
        severity="medium",
        column_id=col.id,
        row_ids=[row.id],
        status="open",
        assignee_id=user.id,
        description="Mixed currency formats detected in Amount column",
    )
    db_session.add(issue)

    # 11. Create Report
    report = Report(
        project_id=project.id,
        dataset_version_id=version.id,
        title="Q3 Executive Revenue Summary",
        status="draft",
        layout_json={"blocks": [{"type": "kpi", "metric": "total_revenue"}]},
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    # 12. Create Comment
    comment = Comment(
        target_type="report",
        target_id=report.id,
        author_id=user.id,
        body="Please verify the currency conversion rate.",
    )
    db_session.add(comment)

    # 13. Create Approval
    approval = Approval(
        report_id=report.id,
        reviewer_id=user.id,
        decision="approved",
        note="Numbers look clean and verified.",
    )
    db_session.add(approval)

    # 14. Create AuditLog
    audit = AuditLog(
        workspace_id=ws.id,
        actor_id=user.id,
        action="report.approved",
        payload_json={"report_id": report.id},
    )
    db_session.add(audit)
    db_session.commit()

    # Query and assert relationships
    queried_user = db_session.query(User).filter_by(id=user.id).first()
    assert queried_user is not None
    assert len(queried_user.memberships) == 1
    assert queried_user.memberships[0].workspace.name == "Acme Analytics"

    queried_dataset = db_session.query(Dataset).filter_by(id=dataset.id).first()
    assert len(queried_dataset.versions) == 1
    assert len(queried_dataset.columns) == 1
    assert len(queried_dataset.rows) == 1
    assert queried_dataset.rows[0].raw_json["Amount"] == "$1,200.50"


def test_json_column_integrity_and_complex_data(db_session):
    """Verify that JSON columns preserve structure, nested types, and array indexing."""
    ws = Workspace(name="JSON Test Workspace")
    db_session.add(ws)
    db_session.commit()

    proj = Project(workspace_id=ws.id, name="JSON Test Project")
    db_session.add(proj)
    db_session.commit()

    dataset = Dataset(
        project_id=proj.id,
        name="test_json.csv",
        source_type="csv",
        raw_file_path="/tmp/test_json.csv",
    )
    db_session.add(dataset)
    db_session.commit()

    # Column with detailed stats JSON
    stats_payload = {
        "null_count": 5,
        "null_pct": 0.05,
        "distinct_count": 95,
        "top_values": [{"val": "A", "count": 20}, {"val": "B", "count": 15}],
        "format_patterns": {"99/99/9999": 90, "YYYY-MM-DD": 10},
    }
    col = ColumnModel(
        dataset_id=dataset.id,
        name="complex_col",
        inferred_type="mixed",
        stats_json=stats_payload,
    )
    db_session.add(col)

    # Row with nested JSON structure in raw_json
    nested_raw = {
        "id": 101,
        "customer": {"name": "Alice", "tags": ["vip", "enterprise"]},
        "flags": [True, False, True],
        "metadata": None,
    }
    row = RowModel(dataset_id=dataset.id, row_index=0, raw_json=nested_raw)
    db_session.add(row)
    db_session.commit()

    # Query back and verify fidelity
    queried_col = db_session.query(ColumnModel).filter_by(id=col.id).first()
    assert queried_col.stats_json["null_count"] == 5
    assert queried_col.stats_json["top_values"][0]["val"] == "A"
    assert queried_col.stats_json["format_patterns"]["99/99/9999"] == 90

    queried_row = db_session.query(RowModel).filter_by(id=row.id).first()
    assert queried_row.raw_json["customer"]["name"] == "Alice"
    assert "vip" in queried_row.raw_json["customer"]["tags"]
    assert queried_row.raw_json["flags"] == [True, False, True]


def test_cascade_deletes_and_constraints(db_session):
    """Verify foreign key cascading deletion and constraint integrity."""
    ws = Workspace(name="Cascade Test Workspace")
    db_session.add(ws)
    db_session.commit()

    proj = Project(workspace_id=ws.id, name="Cascade Project")
    db_session.add(proj)
    db_session.commit()

    dataset = Dataset(
        project_id=proj.id,
        name="cascade_ds.csv",
        source_type="csv",
        raw_file_path="/tmp/cascade.csv",
    )
    db_session.add(dataset)
    db_session.commit()

    ds_id = dataset.id
    proj_id = proj.id

    # Verify entities exist
    assert db_session.query(Project).filter_by(id=proj_id).first() is not None
    assert db_session.query(Dataset).filter_by(id=ds_id).first() is not None

    # Deleting workspace must cascade and delete project and dataset
    db_session.delete(ws)
    db_session.commit()

    assert db_session.query(Project).filter_by(id=proj_id).first() is None
    assert db_session.query(Dataset).filter_by(id=ds_id).first() is None
