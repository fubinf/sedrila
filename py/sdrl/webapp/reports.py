"""Report pages: index (work report) and bonus report."""
import html

import bottle  # https://bottlepy.org/docs/dev/

import base as b
import sdrl.participant

from sdrl.webapp.resources import BONUS_REPORT_URL, MANUAL_BOOKINGS_URL
from sdrl.webapp.app import html_for_layout


@bottle.route("/")
def serve_index():
    ctx = sdrl.participant.get_context()
    body = f"""
        <main id="index-layout">
            <section class="scroll" id="work-report">
                <div class="legend-grid">
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-check"></span>
                    <span>CHECK</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-reject"></span>
                    <span>Rejected</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-accept"></span>
                    <span>Accepted</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-unchecked"></span>
                    <span>Not submitted</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-reject final"></span>
                    <span>Rejected (Final)</span>
                  </div>
                  <div class="legend-item">
                    <span class="legend-swatch indicator-bar task-accept past"></span>
                    <span>Accepted (Past)</span>
                  </div>
                </div>
                <p>Select a task on the left, switch between its files at the top, select choice at bottom right.</p>
                <h2>Work Report</h2>
                {html_for_work_progress(ctx)}
                <p><b>w</b>: work time (from commit msgs), <b>v</b>: task time value, <b>e</b>: estimated time (if task is accepted), <b>m</b>: manual bookings</p>
                {html_for_work_report_section(ctx)}
            </section>
            <section class="scroll" id="students-table">
                <h2>Student{"s" if len(ctx.studentlist) != 1 else ""}</h2>
                {html_for_student_table(ctx.studentlist)}
            </section>
        </main>
    """
    return html_for_layout("sedrila", body)


@bottle.route(BONUS_REPORT_URL)
def serve_bonus_report():
    ctx = sdrl.participant.get_context()
    return html_for_layout("Bonus Report", f"<main><section>{html_for_bonus_report(ctx)}</section></main>")


@bottle.route(MANUAL_BOOKINGS_URL)
def serve_manual_bookings():
    ctx = sdrl.participant.get_context()
    return html_for_layout("Manual Bookings", f"<main><section>{html_for_manual_bookings(ctx)}</section></main>")


def html_for_student_table(studentlist: list[sdrl.participant.Student]) -> str:
    tables = "".join(f"""
        <div class="student-card">
            <div class="student-name">
                {html.escape(s.student_name)} ({html.escape(s.student_id)})
            </div>
            <hr/>
            <div class="student-git">Git: {html.escape(s.student_gituser)}</div>
            <div class="partner-git">
                Partner: {html.escape(s.partner_gituser or "< none >")}
            </div>
        </div>
    """ for s in studentlist)

    return f"""
        <div>
            {tables}
        </div>
    """


def html_for_work_progress(ctx: sdrl.participant.Context) -> str:
    if len(set(map(lambda s: s.student_gituser, ctx.studentlist))) != len(ctx.studentlist):
        b.warning("multiple students with same git username work report might be incorrect!")
    check_work = {s.student_gituser: .0 for s in ctx.studentlist}
    notsubmitted_work = {s.student_gituser: .0 for s in ctx.studentlist}

    from sdrl.webapp.app import ordered_task_entries
    entries = ordered_task_entries(ctx.course, ctx.tasknames)
    for kind, name in entries:
        if kind != 'task':
            continue
        for s in ctx.studentlist:
            ct = s.submissions.task(name)
            tsk = s.course.task(name)
            if ct:
                if ct.state is None:
                    notsubmitted_work[s.student_gituser] += tsk.timevalue
                if ct.state == sdrl.participant.SubmissionTaskState.CHECK:
                    check_work[s.student_gituser] += tsk.timevalue

    tables = "".join(f"""
            <div class="progress-card">
                <div class="student-name">
                    {html.escape(s.student_gituser)}
                </div>
                <hr/>
                <div>CHECK: {round(check_work[s.student_gituser], 2)}</div>
                <div>Not submitted: {round(notsubmitted_work[s.student_gituser], 2)}</div>
            </div>
        """ for s in ctx.studentlist)
    return (f"""
            <div style="width: 13em;">
            <b>Current work period:</b><br>
                {tables}
            </div>
        """)


def html_for_work_report_section(ctx: sdrl.participant.Context) -> str:
    if len(set(map(lambda s: s.student_gituser, ctx.studentlist))) != len(ctx.studentlist):
        b.warning("multiple students with same git username work report might be incorrect!")
    total_earned = { s.student_gituser: .0 for s in ctx.studentlist}
    total_work = { s.student_gituser: .0 for s in ctx.studentlist }
    est_work = {s.student_gituser: .0 for s in ctx.studentlist}
    total_manual = {s.student_gituser: .0 for s in ctx.studentlist}

    def html_for_students(task: str) -> str:
        markup = []
        for i, s in enumerate(ctx.studentlist):
            ct = s.course.task(task) # course_task
            if ct:
                total_earned[s.student_gituser] += ct.time_earned
                total_work[s.student_gituser] += ct.workhours
                est_work[s.student_gituser] += ct.timevalue
                total_manual[s.student_gituser] += ct.manual_timevalue

            manual_val = round(ct.manual_timevalue, 2) if ct and ct.manual_timevalue else ""
            markup.append(f"""
                <td>{round(ct.workhours, 2) if ct and ct.workhours else ""}</td>
                <td>{round(ct.time_earned, 2) if ct and ct.time_earned else ""}</td>
                <td>{round(ct.timevalue, 2) if ct and ct.timevalue else ""}</td>
                <td>{manual_val}</td>
            """)
            if i < len(ctx.studentlist) - 1:
                markup.append("<td></td>")

        return "".join(markup)

    tasks_markup = []
    from sdrl.webapp.app import ordered_task_entries
    entries = ordered_task_entries(ctx.course, ctx.tasknames)
    task_index = 0
    for kind, name in entries:
        if kind == 'chapter':
            tasks_markup.append(f"""
            <tr class="work-report-chapter-row"><td class="work-report-chapter-cell" colspan="100">{name}</td></tr>""")
        elif kind == 'taskgroup':
            tasks_markup.append(f"""
            <tr class="work-report-taskgroup-row"><td class="work-report-taskgroup-cell" colspan="100">{name}</td></tr>""")
        else:
            tasks_markup.append(f"""
            <tr class="{'even' if task_index % 2 == 0 else 'odd'}">
                <td>{name}</td>
                {html_for_students(name)}
            </tr>""")
            task_index += 1

    students_markup = []
    totals_markup = []
    for i, s in enumerate(ctx.studentlist):
        students_markup.append(f"""
        <th colspan="4">{s.student_gituser}</th>
        """)
        # In totals row, leave m empty; add manual total to v (earned)
        course_manual = s.course_with_work.manual_timevalue
        totals_markup.append(f"""
        <td>{round(total_work[s.student_gituser], 2)}</td>
        <td>{round(total_earned[s.student_gituser] + course_manual, 2)}</td>
        <td>{round(est_work[s.student_gituser], 2)}</td>
        <td></td>
        """)
        if i < len(ctx.studentlist) - 1:
            students_markup.append("<th>&nbsp;</th>")
            totals_markup.append("<td></td>")

    # Bonus row (only if bonusrules are configured)
    bonus_row = ""
    if ctx.course.bonusrules is not None:
        import sdrl.course_si
        br = ctx.course.bonusrules
        attr = br['student_yaml_attribute']
        bonus_cells = []
        for i, s in enumerate(ctx.studentlist):
            raw = s.participant_data.get(attr)
            if raw is not None:
                course_size_hours = float(raw)
                results = s.course_with_work.compute_bonus(course_size_hours)
                tb = sdrl.course_si.CourseSI.total_bonus(results)
                bonus_cells.append(f"<td></td><td>{round(tb, 2) if tb else ''}</td><td></td><td></td>")
            else:
                bonus_cells.append("<td></td><td></td><td></td><td></td>")
            if i < len(ctx.studentlist) - 1:
                bonus_cells.append("<td></td>")
        bonus_row = f"""
            <tr>
                <td><i><a href='{BONUS_REPORT_URL}'>Bonus</a></i></td>
                {''.join(bonus_cells)}
            </tr>
        """

    # "Other manual bookings" row (if manual_bookings is configured)
    manual_row = ""
    if ctx.course.manual_booking_types:
        manual_cells = []
        has_any_global_manual = False
        for i, s in enumerate(ctx.studentlist):
            cw = s.course_with_work
            task_manual_sum = sum(t.manual_timevalue for t in cw.taskdict.values())
            global_manual = cw.manual_timevalue - task_manual_sum
            if global_manual:
                has_any_global_manual = True
            manual_cells.append(f"<td></td><td></td><td></td><td>{round(global_manual, 2) if global_manual else ''}</td>")
            if i < len(ctx.studentlist) - 1:
                manual_cells.append("<td></td>")
        if has_any_global_manual:
            manual_row = f"""
                <tr>
                    <td><i>other <a href='{MANUAL_BOOKINGS_URL}'>manual bookings</a></i></td>
                    {''.join(manual_cells)}
                </tr>
            """

    return f"""
        <table id="work-table">
            <tr>
                <th></th>
                {''.join(students_markup)}
            </tr>
            <tr>
                <th>task</th>
                {"<th></th>".join(["<th>w</th><th>v</th><th>e</th><th>m</th>"] * len(ctx.studentlist))}
            </tr>
            {''.join(tasks_markup)}
            {bonus_row}
            {manual_row}
            <tr>
            <td>totals (worked, earned, estimated)</td>
            {''.join(totals_markup)}
            </tr>
        </table>
    """


def html_for_bonus_report(ctx: sdrl.participant.Context) -> str:
    """HTML body for the bonus detail page."""
    import sdrl.course_si
    course = ctx.course
    br = course.bonusrules
    if br is None:
        return "<p>No bonus rules configured for this course.</p>"
    period_type = br['bonusperiod_type']
    threshold = br['bonus_threshold_percent']
    bonus_size = br['bonus_size_percent']
    n = br['bonusperiods']
    attr = br['student_yaml_attribute']

    # Per-student results
    student_results: list[tuple[sdrl.participant.Student, list[sdrl.course_si.BonusPeriodResult]]] = []
    for s in ctx.studentlist:
        raw = s.participant_data.get(attr)
        if raw is not None:
            csz = float(raw)
            results = s.course_with_work.compute_bonus(csz)
        else:
            results = []
        student_results.append((s, results))

    # Rules explanation
    rules_html = f"""
        <div>
            <h2>Bonus Rules</h2>
            <p>Each of the first <b>{n} {period_type}s</b> of the course can produce a bonus.
            A period earns a bonus ({bonus_size}% of your course size in hours) if:</p>
            <ul>
                <li>You earned at least <b>{threshold}%</b> of your course size in that period, OR</li>
                <li>Your cumulative total up to the end of that period is at least
                    <b>{threshold}% &times; period&nbsp;number</b> of your course size.</li>
            </ul>
        </div>
    """

    # Column legend
    legend_html = """
        <div>
            <h2>Bonus Details</h2>
            <p> Columns:
                <b>p#</b>: period number &nbsp;
                <b>period</b>: period name or end date &nbsp;
                <b>ph</b>: hours accepted in this period &nbsp;
                <b>p%</b>: period hours as % of course size &nbsp;
                <b>ch</b>: cumulative hours accepted up to end of period &nbsp;
                <b>c%</b>: cumulative hours as % of course size &nbsp;
                <b>bh</b>: bonus hours for this period
            </p>
        </div>
    """

    # Collect all period labels from first student that has results (same for all who do)
    all_labels = []
    for s, results in student_results:
        if results:
            course_obj = s.course_with_work
            ranges = course_obj.bonus_period_ranges()
            for p_idx, (pstart, pend) in enumerate(ranges):
                all_labels.append((p_idx + 1, course_obj.bonus_period_label(pstart, pend)))
            break

    def fmt(val: float) -> str:
        return ("%.1f" % val) if val else ""

    # Header row
    student_headers = "<th>&nbsp;</th>".join(
        f"<th colspan='5'>{html.escape(s.student_gituser)}</th>"
        for s, _ in student_results
    )
    sub_headers = "<th></th>".join(["<th>ph</th><th>p%</th><th>ch</th><th>c%</th><th>bh</th>"] * len(student_results))

    # Data rows
    rows_html_parts = []
    for i, (p_num, label) in enumerate(all_labels):
        cells = []
        for j, (s, results) in enumerate(student_results):
            if p_num - 1 < len(results) and results[p_num - 1].period_hours:
                r = results[p_num - 1]
                cells.append(
                    f"<td>{fmt(r.period_hours)}</td>"
                    f"<td>{fmt(r.period_percent)}</td>"
                    f"<td>{fmt(r.cumulative_hours)}</td>"
                    f"<td>{fmt(r.cumulative_percent)}</td>"
                    f"<td>{fmt(r.bonus_hours)}</td>"
                )
            else:
                cells.append("<td></td><td></td><td></td><td></td><td></td>")
            if j < len(student_results) - 1:
                cells.append("<td></td>")
        rows_html_parts.append(f"""
            <tr class="{'even' if i % 2 == 0 else 'odd'}">
                <td>{p_num}</td>
                <td>{html.escape(label)}</td>
                {''.join(cells)}
            </tr>
        """)

    # Total row
    total_cells = []
    for j, (s, results) in enumerate(student_results):
        tb = sdrl.course_si.CourseSI.total_bonus(results)
        total_cells.append(f"<td></td><td></td><td></td><td></td><td>{fmt(tb)}</td>")
        if j < len(student_results) - 1:
            total_cells.append("<td></td>")

    table_html = f"""
        <div>
            <table id="work-table">
                <tr>
                    <th colspan="2"></th>
                    {student_headers}
                </tr>
                <tr>
                    <th>p#</th><th>period</th>
                    {sub_headers}
                </tr>
                {''.join(rows_html_parts)}
                <tr>
                    <td colspan="2"><b>Total bonus</b></td>
                    {''.join(total_cells)}
                </tr>
            </table>
        </div>
    """

    return rules_html + legend_html + table_html


def html_for_manual_bookings(ctx: sdrl.participant.Context) -> str:
    """HTML body for the manual bookings detail page."""
    booking_types = ctx.course.manual_booking_types
    mb_config = ctx.course.configdict.get('manual_bookings')
    explanation_url = mb_config['explanation_url'] if mb_config else ''
    sections = ["<p>Manual bookings are made by instructors when special circumstances occur.</p>\n"]
    if mb_config:
        sections.append(f"<p>These are described on <a href='{explanation_url}'>{explanation_url}</a>.</p>")
    else:
        sections.append(f"<p>This functionality is not configured for the present course.</p>")
    for s in ctx.studentlist:
        cw = s.course_with_work
        bookings = getattr(cw, 'manual_bookings', [])
        if not bookings:
            sections.append(f"<h3>{html.escape(s.student_gituser)}</h3><p>No manual bookings.</p>")
            continue
        sorted_bookings = sorted(bookings, key=lambda e: e.commit.author_date)
        rows = []
        for i, entry in enumerate(sorted_bookings):
            reason_escaped = html.escape(entry.reason)
            if entry.reason in cw.taskdict:
                reason_display = f"T::{reason_escaped}"
            elif entry.reason in booking_types:
                reason_display = f"<a href='{html.escape(explanation_url)}#{html.escape(entry.reason)}'>{reason_escaped}</a>"
            else:
                reason_display = reason_escaped
            date = entry.commit.author_date.strftime("%Y-%m-%d")
            commit_hash = entry.commit.hash[:10]
            rows.append(f"""
                <tr class="{'even' if i % 2 == 0 else 'odd'}">
                    <td>{reason_display}</td>
                    <td>{date}</td>
                    <td>{commit_hash}</td>
                    <td>{entry.timevalue}</td>
                </tr>
            """)
        sections.append(f"""
            <h3>{html.escape(s.student_gituser)}</h3>
            <table id="work-table">
                <tr><th>Reason</th><th>Date</th><th>Commit</th><th>Timevalue</th></tr>
                {''.join(rows)}
            </table>
        """)
    return "<h2>Manual Bookings</h2>" + "".join(sections)
