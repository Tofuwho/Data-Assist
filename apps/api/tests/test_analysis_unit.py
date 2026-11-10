from datetime import UTC, datetime

from app.models.entities import ColumnModel, Dataset, DatasetVersion, Issue
from app.services.ai import (
    MockLLMClient,
    generate_report_narrative,
    get_llm_client,
    verify_narrative_numbers,
)
from app.services.analysis import (
    EffectiveDataset,
    EffectiveRow,
    analyze_dataset,
    recommend_report_layout,
)


def _make_effective_sales_fixture() -> EffectiveDataset:
    ds = Dataset(
        id="ds-sales-1",
        project_id="proj-1",
        name="Q1 Sales",
        source_type="csv",
        raw_file_path="sales.csv",
        status="ready",
    )
    ver = DatasetVersion(
        id="ver-1",
        dataset_id=ds.id,
        version_number=1,
        note="Original import",
        created_at=datetime.now(UTC),
    )
    cols = [
        ColumnModel(id="c1", dataset_id=ds.id, name="Transaction_ID", position=0, inferred_type="identifier", semantic_hint="identifier"),
        ColumnModel(id="c2", dataset_id=ds.id, name="Date", position=1, inferred_type="date", semantic_hint="date"),
        ColumnModel(id="c3", dataset_id=ds.id, name="Amount", position=2, inferred_type="currency", semantic_hint="amount"),
        ColumnModel(id="c4", dataset_id=ds.id, name="Region", position=3, inferred_type="category", semantic_hint="region"),
        ColumnModel(id="c5", dataset_id=ds.id, name="Status", position=4, inferred_type="category", semantic_hint="status"),
    ]
    raw_records = [
        ("TX1", "2024-01-10", "$1,000.00", "NY", "Completed"),
        ("TX2", "2024-01-12", "500 USD", "NY", "Completed"),
        ("TX3", "03/04/2024", "€800.00", "CA", "Completed"),  # ambiguous date & EUR
        ("TX4", "2024-01-15", "bad_amt", "CA", "Failed"),  # unparseable amount
        ("TX5", "2024-01-20", "$2,500.00", "", "Pending"),  # empty region
    ]
    rows = [
        EffectiveRow(
            id=f"r-{i}",
            row_index=i,
            raw_values={
                "Transaction_ID": tid,
                "Date": dt,
                "Amount": amt,
                "Region": reg,
                "Status": st,
            },
            values={
                "Transaction_ID": tid,
                "Date": dt,
                "Amount": amt,
                "Region": reg,
                "Status": st,
            },
        )
        for i, (tid, dt, amt, reg, st) in enumerate(raw_records)
    ]
    issues = [
        Issue(
            id="iss-1",
            dataset_id=ds.id,
            type="mixed_formats",
            severity="high",
            column_id="c2",
            status="open",
            description="Ambiguous date format detected",
            affected_count=1,
        )
    ]
    return EffectiveDataset(
        dataset=ds,
        version=ver,
        columns=cols,
        columns_by_name={c.name: c for c in cols},
        columns_by_id={c.id: c for c in cols},
        issues=issues,
        rows=rows,
    )


def test_analyzer_metrics_ambiguous_dates_and_caveats():
    effective = _make_effective_sales_fixture()
    analysis = analyze_dataset(effective)

    assert analysis["overview"]["row_count"] == 5
    assert analysis["overview"]["column_count"] == 5
    assert analysis["primary_measure"]["column"] == "Amount"
    # Valid amounts: 1000 + 500 + 800 + 2500 = 4800.0; TX4 'bad_amt' excluded
    assert analysis["primary_measure"]["sum"] == 4800.0
    assert analysis["primary_measure"]["valid_count"] == 4
    assert analysis["primary_measure"]["unparseable_count"] == 1

    # Ambiguous date 03/04/2024 must NOT be guessed into time series
    ts = analysis["time_series"]
    assert ts is not None
    assert ts["valid_date_count"] == 4
    assert ts["ambiguous_skipped_count"] == 1

    caveat_categories = {c["category"] for c in analysis["data_quality_caveats"]}
    assert "ambiguous_dates" in caveat_categories
    assert "mixed_currency" in caveat_categories
    assert "unparseable_numeric" in caveat_categories

    title, layout = recommend_report_layout(effective, analysis, template="auto")
    assert layout["template"] == "executive_sales"
    assert "Executive Performance" in title
    block_types = [b["type"] for b in layout["blocks"]]
    assert "narrative" in block_types
    assert "kpi" in block_types
    assert "line_chart" in block_types
    assert "bar_chart" in block_types
    assert "data_quality" in block_types


def test_mock_llm_client_narrative_is_strictly_grounded():
    effective = _make_effective_sales_fixture()
    analysis = analyze_dataset(effective)
    title, layout = recommend_report_layout(effective, analysis, template="executive_sales")

    # Build lightweight computed KPI summary for packet
    computed_blocks = [
        {
            "id": "blk_kpi_1",
            "type": "kpi",
            "title": "Total Amount",
            "data": {
                "value": 4800.0,
                "formatted_value": "$4,800.00",
                "aggregation": "sum",
                "matching_rows": 4,
                "excluded_rows": 1,
            },
        }
    ]
    client = get_llm_client("mock")
    assert isinstance(client, MockLLMClient)

    narrative = generate_report_narrative(title, effective.dataset.name, analysis, computed_blocks, client=client)
    assert narrative["verification"]["verified"] is True, narrative["verification"]
    assert narrative["verification"]["unverified_numbers"] == []
    assert "4,800.00" in narrative["headline"] or "4,800.00" in narrative["executive_summary"]


class _HallucinatingLLMClient:
    provider_name = "fake_hallucinator"
    model_name = "fake-1"

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        return {
            "headline": "Revenue surged to $999,999.00 in Q1",
            "executive_summary": "Sales grew by 87.5% across 420 customers.",
            "key_findings": ["Unverified projection of 12,345 units sold."],
            "recommendations": ["Expand immediately."],
            "caveats": ["No issues found."],
        }


def test_narrative_verifier_flags_hallucinated_numbers():
    effective = _make_effective_sales_fixture()
    analysis = analyze_dataset(effective)
    title, _ = recommend_report_layout(effective, analysis)

    narrative = generate_report_narrative(
        title,
        effective.dataset.name,
        analysis,
        [],
        client=_HallucinatingLLMClient(),
    )
    assert narrative["verification"]["verified"] is False
    unverified = " ".join(narrative["verification"]["unverified_numbers"])
    assert "999,999.00" in unverified
    assert "87.5%" in unverified
    assert "420" in unverified
    assert "12,345" in unverified


def test_verify_narrative_numbers_direct_edge_cases():
    packet = {
        "overview": {"row_count": 15, "completeness_pct": 97.14},
        "primary_measure": {"sum": 39770.5, "mean": 2840.75},
        "time_series": {"start_period": "2024-01-15", "end_period": "2024-01-28"},
    }
    good = {
        "headline": "Total is $39,770.50 across 15 rows (97.14% complete)",
        "executive_summary": "From 2024-01-15 to 2024-01-28 mean reached $2,840.75.",
        "key_findings": [],
        "recommendations": [],
        "caveats": [],
    }
    res_good = verify_narrative_numbers(good, packet)
    assert res_good["verified"] is True

    bad_date = {
        **good,
        "executive_summary": "From 2029-12-31 mean reached $2,840.75.",
    }
    res_bad = verify_narrative_numbers(bad_date, packet)
    assert res_bad["verified"] is False
    assert "2029-12-31" in res_bad["unverified_numbers"]
