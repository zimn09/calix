"""Sidebar panels: skill details and the profile dashboard."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from graph import level_info
from skills_data import CATEGORIES, TIERS
from theme import STATUS_COLORS, STATUS_LABELS

READINESS_NOTE = (
    "Unlocking a skill only means its prerequisites are ticked off. It does not mean your tendons, "
    "joints and technique are ready. Progress in small steps, warm up, and stop if something hurts. "
    "If you have an injury or health condition, check with a coach or physician."
)


def _h(text, color="#8b95a7"):
    return (f'<p style="margin-top:12px;margin-bottom:2px"><b><span style="color:{color};'
            f'font-size:9pt;letter-spacing:1px">{text.upper()}</span></b></p>')


def _fmt(v, unit):
    return f"{v:g} {unit}".strip()


class DetailPanel(QWidget):
    statusRequested = Signal(str, object)   # skill id, new status (or None to clear)
    recordLogged = Signal(str, float)
    skillLink = Signal(str)

    def __init__(self, graph, store, parent=None):
        super().__init__(parent)
        self.graph, self.store = graph, store
        self.sid = None
        self.progress = {}
        self.rank_provider = None      # callable(skill id) -> list of HTML lines, set by the main window
        self.achievement_provider = None   # same, for achievements related to the skill

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        self.title = QLabel("Select a skill")
        self.title.setObjectName("skillTitle")
        self.title.setWordWrap(True)
        self.badges = QLabel()
        self.badges.setTextFormat(Qt.RichText)

        self.body = QTextBrowser()
        self.body.setOpenLinks(False)
        self.body.anchorClicked.connect(self._on_link)

        self.pr_box = QGroupBox("Personal record")
        pr = QVBoxLayout(self.pr_box)
        self.pr_label = QLabel()
        self.pr_label.setTextFormat(Qt.RichText)
        self.pr_label.setWordWrap(True)
        row = QHBoxLayout()
        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(0)
        self.spin.setRange(0, 9999)
        self.btn_log = QPushButton("Log record")
        self.btn_log.clicked.connect(self._log)
        row.addWidget(self.spin, 1)
        row.addWidget(self.btn_log)
        pr.addWidget(self.pr_label)
        pr.addLayout(row)

        btns = QHBoxLayout()
        self.btn_train = QPushButton("Start training")
        self.btn_train.setObjectName("primary")
        self.btn_train.clicked.connect(self._toggle_train)
        self.btn_done = QPushButton("Mark completed")
        self.btn_done.setObjectName("success")
        self.btn_done.clicked.connect(self._toggle_done)
        btns.addWidget(self.btn_train)
        btns.addWidget(self.btn_done)

        lay.addWidget(self.title)
        lay.addWidget(self.badges)
        lay.addWidget(self.body, 1)
        lay.addWidget(self.pr_box)
        lay.addLayout(btns)
        self.render()

    # ----------------------------------------------------------------- API
    def show_skill(self, sid, progress=None):
        changed = sid != self.sid
        self.sid = sid
        if progress is not None:
            self.progress = progress
        self.render(reset_spin=changed)

    def set_progress(self, progress):
        self.progress = progress
        self.render()

    # ------------------------------------------------------------- handlers
    def _on_link(self, url):
        s = url.toString()
        if s.startswith("skill:"):
            self.skillLink.emit(s[6:])

    def _status(self):
        return self.graph.status(self.sid, self.progress)

    def _toggle_train(self):
        if self.sid:
            self.statusRequested.emit(self.sid, None if self._status() == "training" else "training")

    def _toggle_done(self):
        if self.sid:
            self.statusRequested.emit(self.sid, None if self._status() == "completed" else "completed")

    def _log(self):
        if self.sid and self.spin.value() > 0:
            self.recordLogged.emit(self.sid, self.spin.value())

    # --------------------------------------------------------------- render
    def render(self, reset_spin=False):
        if not self.sid:
            self.badges.setText("")
            self.body.setHtml('<p style="color:#8b95a7">Click any node in the tree to see its description, '
                              'progression steps, recommended training and prerequisites.</p>'
                              f'<p style="color:#6b7686"><i>{READINESS_NOTE}</i></p>')
            self.pr_box.hide()
            self.btn_train.setEnabled(False)
            self.btn_done.setEnabled(False)
            return

        g = self.graph
        s = g.skills[self.sid]
        st = self._status()
        cat_label, cat_color = CATEGORIES[s.category]
        self.title.setText(s.name)
        self.badges.setText(
            f'<span style="color:{cat_color}">●&nbsp;{cat_label}</span> &nbsp; '
            f'<span style="color:#9aa4b2">◆&nbsp;{TIERS[s.tier]}</span> &nbsp; '
            f'<span style="color:{STATUS_COLORS[st]}"><b>{STATUS_LABELS[st]}</b></span>')
        self.body.setHtml(self._html(s, st, cat_color))

        # buttons
        self.btn_train.setText("Stop training" if st == "training" else "Start training")
        self.btn_train.setEnabled(st in ("available", "training"))
        self.btn_done.setText("Mark incomplete" if st == "completed" else "Mark completed")
        self.btn_done.setEnabled(st != "locked")

        # personal record
        if s.target > 0:
            self.pr_box.show()
            self.pr_box.setTitle(f"Personal record ({s.unit})")
            best = self.store.best(self.sid)
            hist = self.store.history(self.sid, 4)
            txt = f"Benchmark: <b>{_fmt(s.target, s.unit)}</b>"
            if best is not None:
                pct = min(100, round(best / s.target * 100))
                reached = " &nbsp;<span style='color:#69db7c'>✓ benchmark reached</span>" if best >= s.target else ""
                txt += f" &nbsp;·&nbsp; Best: <b>{_fmt(best, s.unit)}</b> ({pct}%){reached}"
                txt += "<br><span style='color:#8b95a7'>Recent: " + ", ".join(
                    f"{v:g} ({d[5:]})" for v, d in hist) + "</span>"
            else:
                txt += "<br><span style='color:#8b95a7'>No record logged yet.</span>"
            self.pr_label.setText(txt)
            if reset_spin:
                self.spin.setValue(best or 0)
            self.spin.setSuffix(f" {s.unit}")
        else:
            self.pr_box.hide()

    def _html(self, s, st, accent):
        g, prog = self.graph, self.progress

        def link(sid):
            col = STATUS_COLORS[g.status(sid, prog)]
            return f'<a href="skill:{sid}" style="color:{col};text-decoration:none">{g.skills[sid].name}</a>'

        out = [f'<p style="color:#c9d1d9;line-height:130%">{s.description}</p>']

        if s.prereqs:
            out.append(_h("Prerequisites", accent))
            for p in s.prereqs:
                mark = "✓" if prog.get(p) == "completed" else "○"
                out.append(f"{mark}&nbsp; {link(p)}<br>")
            if st == "locked":
                out.append('<p style="color:#ff8787">Locked. Complete the prerequisites above to unlock this skill.</p>')
        else:
            out.append(_h("Starting point", accent))
            out.append('<p style="color:#c9d1d9">No prerequisites. You can begin here.</p>')

        lines = self.rank_provider(s.id) if self.rank_provider else []
        if lines:
            out.append(_h("Rank", accent))
            out.append("".join(f"{x}<br>" for x in lines))

        ach = self.achievement_provider(s.id) if self.achievement_provider else []
        if ach:
            out.append(_h("Achievements", accent))
            out.append("".join(f"{x}<br>" for x in ach))

        out.append(_h("Progression steps", accent))
        out.append("<ol style='margin-top:2px'>" + "".join(f"<li>{x}</li>" for x in s.steps) + "</ol>")
        out.append(_h("Recommended training", accent))
        out.append("<ul style='margin-top:2px'>" + "".join(f"<li>{x}</li>" for x in s.exercises) + "</ul>")
        if s.regressions:
            out.append(_h("Regressions / easier options", accent))
            out.append("<ul style='margin-top:2px'>" + "".join(f"<li>{x}</li>" for x in s.regressions) + "</ul>")

        kids = g.children.get(s.id, [])
        out.append(_h("Work toward next", accent))
        if kids:
            for k in kids:
                out.append(f"→&nbsp; {link(k)} <span style='color:#6b7686'>({TIERS[g.skills[k].tier]})</span><br>")
        else:
            out.append('<p style="color:#c9d1d9">This is the end of this branch.</p>')

        if s.note:
            out.append(_h("Safety note", "#ffa94d"))
            out.append(f'<p style="color:#ffd8a8">{s.note}</p>')
        out.append(f'<p style="color:#6b7686;margin-top:14px"><i>{READINESS_NOTE}</i></p>')
        return "".join(out)


class StatsPanel(QWidget):
    skillLink = Signal(str)

    def __init__(self, graph, store, level_provider=None, show_level=True, parent=None):
        super().__init__(parent)
        self.graph, self.store = graph, store
        self.level_provider = level_provider      # callable -> XpEngine.profile() dict; replaces the old skill-only level
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        self.level = QLabel()
        self.level.setObjectName("levelLabel")
        self.xp_bar = QProgressBar()
        self.xp_bar.setTextVisible(False)
        self.xp_bar.setStyleSheet("QProgressBar::chunk { background: #ffd43b; }")
        self.xp_label = QLabel()
        self.xp_label.setObjectName("muted")
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        self.summary.setWordWrap(True)

        if show_level:
            lay.addWidget(self.level)
            lay.addWidget(self.xp_bar)
            lay.addWidget(self.xp_label)
        lay.addWidget(self.summary)

        self.cat_bars, self.cat_labels = {}, {}
        for key, (label, color) in CATEGORIES.items():
            row = QHBoxLayout()
            name = QLabel(label)
            name.setFixedWidth(95)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")
            cnt = QLabel()
            cnt.setObjectName("muted")
            cnt.setFixedWidth(48)
            cnt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(name)
            row.addWidget(bar, 1)
            row.addWidget(cnt)
            lay.addLayout(row)
            self.cat_bars[key], self.cat_labels[key] = bar, cnt

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self._on_link)
        lay.addWidget(self.browser, 1)

    def _on_link(self, url):
        s = url.toString()
        if s.startswith("skill:"):
            self.skillLink.emit(s[6:])

    def refresh(self, progress):
        g = self.graph
        statuses = {sid: g.status(sid, progress) for sid in g.order}
        total = len(statuses)
        done = sum(1 for v in statuses.values() if v == "completed")
        training = [s for s, v in statuses.items() if v == "training"]
        avail = [s for s, v in statuses.items() if v == "available"]

        if self.level_provider:
            p = self.level_provider()
            self.level.setText(f"Level {p['level']} · {p['title']}")
            self.xp_bar.setMaximum(1000)
            self.xp_bar.setValue(int(p["progress"] * 1000))
            self.xp_bar.setStyleSheet(f"QProgressBar::chunk {{ background: {p['color']}; }}")
            nxt = f"{p['into']:,}/{p['need']:,} XP to next level" if p["need"] else "max level"
            self.xp_label.setText(f"{p['total']:,} XP total · {nxt} · achievements {p['unlocked']}/{p['count']}")
        else:
            xp = g.xp(progress)
            lvl, into, need, title = level_info(xp)
            self.level.setText(f"Level {lvl} · {title}")
            self.xp_bar.setMaximum(max(1, need))
            self.xp_bar.setValue(into)
            self.xp_label.setText(f"{xp} XP total · {into}/{need} to next level" if need > 1 else f"{xp} XP · max level")
        self.summary.setText(f"{done}/{total} skills completed · {len(training)} training · "
                             f"{len(avail)} available to train · {total - done - len(training) - len(avail)} locked")

        for key in CATEGORIES:
            ids = [s for s in g.order if g.skills[s].category == key]
            c = sum(1 for s in ids if statuses[s] == "completed")
            self.cat_bars[key].setMaximum(len(ids))
            self.cat_bars[key].setValue(c)
            self.cat_labels[key].setText(f"{c}/{len(ids)}")

        def link(sid):
            sk = g.skills[sid]
            return (f'<a href="skill:{sid}" style="color:{CATEGORIES[sk.category][1]};text-decoration:none">'
                    f'{sk.name}</a>')

        html = []
        if training:
            html.append(_h("Currently training"))
            html += [f"▶&nbsp; {link(s)}<br>" for s in training]
        html.append(_h("Next up (unlocked)"))
        order = sorted(avail, key=lambda s: (g.skills[s].tier, g.depth[s]))
        if order:
            html += [f"○&nbsp; {link(s)} <span style='color:#6b7686'>({TIERS[g.skills[s].tier]})</span><br>"
                     for s in order[:8]]
            if len(order) > 8:
                html.append(f"<span style='color:#6b7686'>…and {len(order) - 8} more</span>")
        else:
            html.append("<span style='color:#8b95a7'>Nothing waiting. Start a training skill or mark one complete.</span>")

        bests = self.store.bests()
        html.append(_h("Personal records"))
        if bests:
            for sid, (val, day) in sorted(bests.items(), key=lambda kv: g.skills[kv[0]].name):
                sk = g.skills[sid]
                html.append(f"{link(sid)}: <b>{_fmt(val, sk.unit)}</b> "
                            f"<span style='color:#6b7686'>({day})</span><br>")
        else:
            html.append("<span style='color:#8b95a7'>No records yet. Log them from a skill's detail page.</span>")
        self.browser.setHtml("".join(html))
