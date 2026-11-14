"""Workout statistics, always calculated from saved sessions (no Qt)."""
import datetime as dt
from collections import Counter

from database import fetch_all, fetch_one

DONE = "s.status='completed' AND ss.done=1"


def week_start(d):
    return d - dt.timedelta(days=d.weekday())


def session_dates(db):
    return [dt.date.fromisoformat(r[0]) for r in
            db.execute("SELECT session_date FROM sessions WHERE status='completed'")]


def totals(db):
    n, secs = db.execute("SELECT COUNT(*), COALESCE(SUM(elapsed_sec),0) FROM sessions "
                         "WHERE status='completed'").fetchone()
    sets, reps, hold = db.execute(f"""SELECT COALESCE(SUM(ss.done),0),
        COALESCE(SUM(CASE WHEN ss.kind='reps' THEN ss.reps ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN ss.kind='hold' THEN ss.hold ELSE 0 END),0)
        FROM session_sets ss JOIN sessions s ON s.id=ss.session_id
        WHERE {DONE}""").fetchone()
    return dict(sessions=n, seconds=secs, sets=sets, reps=reps, hold=hold)


def weekly_counts(dates, today, weeks=12):
    c = Counter(week_start(d) for d in dates)
    first = week_start(today) - dt.timedelta(weeks=weeks - 1)
    return [(first + dt.timedelta(weeks=i), c.get(first + dt.timedelta(weeks=i), 0)) for i in range(weeks)]


def avg_per_week(dates, today, weeks=8):
    return sum(n for _, n in weekly_counts(dates, today, weeks)) / weeks


def this_week(dates, today):
    return sum(1 for d in dates if week_start(d) == week_start(today))


def streak(dates, today):
    """Consecutive training days ending today (or yesterday, if today isn't done yet)."""
    days = set(dates)
    d = today if today in days else today - dt.timedelta(days=1)
    n = 0
    while d in days:
        n += 1
        d -= dt.timedelta(days=1)
    return n


def day_counts(dates):
    return dict(Counter(dates))


def most_performed(db, limit=8):
    return fetch_all(db, f"""SELECT MAX(ss.exercise_name) AS name, COUNT(DISTINCT ss.session_id) AS sessions,
        COUNT(*) AS sets FROM session_sets ss JOIN sessions s ON s.id=ss.session_id
        WHERE {DONE} GROUP BY ss.exercise_id ORDER BY sessions DESC, sets DESC, name LIMIT ?""", (limit,))


def personal_records(db):
    """Best single set per exercise: max reps for rep exercises, max hold seconds for holds."""
    rows = fetch_all(db, f"""SELECT ss.exercise_id, MAX(ss.exercise_name) AS name, ss.kind,
        MAX(CASE WHEN ss.kind='reps' THEN ss.reps ELSE ss.hold END) AS best
        FROM session_sets ss JOIN sessions s ON s.id=ss.session_id WHERE {DONE}
        GROUP BY ss.exercise_id, ss.kind HAVING best>0 ORDER BY name""")
    for r in rows:
        col = "reps" if r["kind"] == "reps" else "hold"
        r["unit"] = "reps" if r["kind"] == "reps" else "s"
        r["date"] = fetch_one(db, f"""SELECT s.session_date AS d FROM session_sets ss JOIN sessions s
            ON s.id=ss.session_id WHERE {DONE} AND ss.exercise_id=? AND ss.kind=? AND ss.{col}=?
            ORDER BY s.started LIMIT 1""", (r["exercise_id"], r["kind"], r["best"]))["d"]
    return rows


def completion(db):
    """Planned vs completed sets across finished sessions, and fully completed sessions."""
    row = fetch_one(db, """SELECT COUNT(*) AS planned, COALESCE(SUM(ss.done),0) AS done
        FROM session_sets ss JOIN sessions s ON s.id=ss.session_id WHERE s.status='completed'""")
    full = fetch_one(db, """SELECT COUNT(*) AS n FROM sessions s WHERE s.status='completed' AND NOT EXISTS
        (SELECT 1 FROM session_sets x WHERE x.session_id=s.id AND x.done=0)""")["n"]
    total = fetch_one(db, "SELECT COUNT(*) AS n FROM sessions WHERE status='completed'")["n"]
    return dict(planned=row["planned"], done=row["done"], full=full, sessions=total,
                pct=(100.0 * row["done"] / row["planned"]) if row["planned"] else None)


def adherence(schedule, sessions, today, days=28):
    """(done, scheduled) workouts over the last `days` days, not counting today."""
    start, end = today - dt.timedelta(days=days), today - dt.timedelta(days=1)
    occ = schedule.occurrences(start, end, sessions.completed_on(start, end))
    items = [o for lst in occ.values() for o in lst if not o["is_rest"]]
    return sum(1 for o in items if o["done"]), len(items)
