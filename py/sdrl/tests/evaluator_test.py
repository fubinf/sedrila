import datetime as dt

import pandas as pd

import sdrl.subcmd.evaluator as evaluator
import sdrl.repo as repo


def test_as_events_df_adds_week_and_date_columns():
    startdate = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    events = [
        repo.Event(repo.ET.work, "s1", "s1@example.org",
                   dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc), "A", 1.0),
        repo.Event(repo.ET.accept, "s1", "i@example.org",
                   dt.datetime(2026, 1, 15, tzinfo=dt.timezone.utc), "A", 1.0),
    ]
    df = evaluator.as_events_df(events, startdate)
    assert list(df.week) == [0, 2]
    assert [str(d) for d in df.date] == ["2026-01-01", "2026-01-15"]


def test_fill_all_weeks_fills_gaps_until_max_week():
    weeks_df = pd.DataFrame([
        dict(evtype='work', student='s1', week=0, timevalue=1.0, cumtimevalue=1.0),
        dict(evtype='work', student='s1', week=2, timevalue=2.0, cumtimevalue=3.0),
    ])
    filled_df = pd.DataFrame(evaluator.fill_all_weeks(weeks_df))
    assert list(filled_df.week) == [0, 1, 2]
    assert list(filled_df.timevalue) == [1.0, 0.0, 2.0]


def test_write_report_page_has_overview_and_explanations(tmp_path):
    sections = [
        dict(slug='one', title='First chart', images=['a.png'],
             explanation='Main explanation.', design_notes='Design explanation.'),
    ]
    evaluator.write_report_page(str(tmp_path), sections, "2026-01-01", 2, 5)
    content = (tmp_path / "index.html").read_text(encoding='utf8')
    assert "Overview" in content
    assert "#one" in content
    assert "Main explanation." in content
    assert "Design explanation." in content
