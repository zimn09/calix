"""Calisthenics Skill Tree - entry point.   Run:  python main.py"""
import json
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QCompleter, QFileDialog, QHBoxLayout,
                               QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSplitter,
                               QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

import achievements as AC
from achievements_page import AchievementsPage
from active_page import ActiveWorkoutPage
from audio import AudioEngine, ClickSfxFilter
from builder_page import WorkoutBuilderPage
from dashboard_page import DashboardPage
from database import Store
from exercises_data import EXERCISES
from graph import SkillGraph
from history_page import HistoryPage
from library_page import LibraryPage
from panels import DetailPanel, StatsPanel
from profile_page import ProfilePage
from profile_repo import ProfileRepo
from rank_repo import RankRepo
from rank_widgets import rank_html
from ranks_page import RankPage
from schedule_page import SchedulePage
from scheduling import ScheduleRepo
from sessions import SessionRepo
from settings import Settings
from settings_page import SettingsPage
from skills_data import CATEGORIES, SKILLS, TIERS
from theme import STATUS_LABELS, build_qss
from tree_view import TreeView
from welcome_page import WelcomePage
from workouts import WorkoutRepo
from xp_engine import XpEngine
from xp_widgets import announce_progress, set_animations

PAGES = [("tree", "Skill Tree"), ("library", "Library"), ("builder", "Workout Builder"),
         ("schedule", "Schedule"), ("active", "Active Workout"), ("history", "History"),
         ("dashboard", "Dashboard"), ("ranks", "Ranks"), ("achievements", "Achievements"),
         ("profile", "Profile"), ("settings", "Settings")]

HELP_TEXT = (
    "<b>Navigating</b><br>Drag to pan, scroll to zoom, click a node for details. Hover a node to light up "
    "the path of prerequisites leading to it.<br><br>"
    "<b>Node states</b><br>Grey + lock = locked. Pulsing ring = available to train. Orange play icon = "
    "training. Green check = completed.<br><br>"
    "<b>Unlocking</b><br>A skill unlocks once <i>all</i> of its prerequisites are marked completed. "
    "Unlocked does not mean you're physically ready, so use the regressions and progression steps.<br><br>"
    "<b>Records</b><br>Log reps or hold times on a skill's detail page. Your best values show on the Profile tab.<br><br>"
    "<b>Training</b><br>Build workouts in <i>Workout Builder</i>, plan them in <i>Schedule</i>, run them in "
    "<i>Active Workout</i> and review results in <i>History</i>. Finished sets also update the matching skill's "
    "personal record in the skill tree.<br><br>"
    "<b>Exercise library</b><br>The <i>Library</i> page holds every exercise with its technique, muscle "
    "groups, mistakes, tips and an offline 2D animation. Mark favourites and add moves to a workout "
    "with one click.<br><br>"
    "<b>Profile &amp; progress</b><br>Your local profile (name, fighter, accent colour) is stored on this "
    "computer only - no account, no email. The <i>Profile</i> page shows your level, XP, achievements, "
    "ranks, cosmetics and a progress dashboard built from your real training data.<br><br>"
    "<b>Sound &amp; music</b><br>Buttons pop, and level-ups, achievements and your own confirmations have their "
    "own sounds. Four background tracks (Temple Bells, Iron Forge, Void Drone, Dawn Run) can be picked in "
    "<i>Settings → Sound &amp; Music</i>; Ctrl+M mutes everything. All audio is generated inside the app.<br><br>"
    "<b>Shortcuts</b><br>Alt+1…11 switch sections · Ctrl+F search skills · Ctrl+0 fit tree · Ctrl++ / Ctrl+- zoom · Ctrl+M mute"
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CALIX")
        self.graph = SkillGraph(SKILLS)
        self.store = Store()                      # opens the DB and runs any pending migrations
        self.wrepo = WorkoutRepo(self.store.db)
        self.profiles = ProfileRepo(self.store.db)
        self.srepo = ScheduleRepo(self.store.db)
        self.sess = SessionRepo(self.store, self.wrepo)
        self.ranks = RankRepo(self.store, self.wrepo)
        self.xp = XpEngine(self.store, self.wrepo, self.sess, self.ranks, self.graph)
        self.settings = Settings(self.store.db)
        self.audio = AudioEngine(self.settings)
        self._click_sfx = ClickSfxFilter(self.audio, self)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self._click_sfx)      # every button press gets the short pop
        self._shown = False

        self.view = TreeView(self.graph)
        self.details = DetailPanel(self.graph, self.store)
        self.stats = StatsPanel(self.graph, self.store, self.xp.profile)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.details, "Skill Details")
        self.tabs.addTab(self.stats, "Profile")
        self.tabs.setObjectName("sidebar")

        self.split = QSplitter(Qt.Horizontal)
        self.split.addWidget(self.view)
        self.split.addWidget(self.tabs)
        self.split.setStretchFactor(0, 1)
        self.split.setSizes([1100, 420])
        self.tabs.setMinimumWidth(380)

        tree_page = QWidget()
        tcol = QVBoxLayout(tree_page)
        tcol.setContentsMargins(0, 0, 0, 0)
        tcol.setSpacing(0)
        tcol.addWidget(self._build_tree_toolbar())
        tcol.addWidget(self.split, 1)

        self.builder = WorkoutBuilderPage(self.wrepo, self.ranks, self.xp)
        self.library = LibraryPage(self.wrepo, self.profiles, self.ranks)
        self.profile = ProfilePage(self.store, self.profiles, self.ranks, self.xp, self.sess, self.graph)
        self.schedule = SchedulePage(self.srepo, self.wrepo, self.sess)
        self.active = ActiveWorkoutPage(self.sess, self.wrepo, self.srepo, self.ranks, self.xp)
        self.history = HistoryPage(self.sess, self.srepo)
        self.dashboard = DashboardPage(self.graph, self.store, self.sess, self.srepo, self.ranks, self.xp)
        self.rank_page = RankPage(self.ranks, self.wrepo, self.xp)
        self.achievements_page = AchievementsPage(self.xp)
        self.settings_page = SettingsPage(self.settings, self.audio)
        self.pages = {"tree": tree_page, "library": self.library, "builder": self.builder,
                      "schedule": self.schedule, "active": self.active, "history": self.history,
                      "dashboard": self.dashboard, "ranks": self.rank_page,
                      "achievements": self.achievements_page, "profile": self.profile,
                      "settings": self.settings_page}
        self.stack = QStackedWidget()
        self.stack.setObjectName("pages")
        for key, _ in PAGES:
            self.stack.addWidget(self.pages[key])

        central = QWidget()
        col = QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self.header = self._build_header()
        col.addWidget(self.header)
        col.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.zoom_label = QLabel("")
        self.count_label = QLabel("")
        self.statusBar().addWidget(self.count_label, 1)
        self.statusBar().addPermanentWidget(self.zoom_label)

        self._build_menus()

        self.view.skillClicked.connect(self._on_node_clicked)
        self.view.zoomChanged.connect(lambda z: self.zoom_label.setText(f"Zoom {z * 100:.0f}%"))
        self.details.statusRequested.connect(self._on_status)
        self.details.recordLogged.connect(self._on_record)
        self.details.skillLink.connect(self.goto)
        self.stats.skillLink.connect(self.goto)

        # workout features
        self.builder.workoutsChanged.connect(self._workouts_changed)
        self.builder.startWorkout.connect(lambda wid: self._start(wid, None))
        self.builder.openLibrary.connect(self._open_in_library)
        self.library.addToWorkout.connect(self._add_to_workout)
        self.library.message.connect(self._toast)
        self.profile.profileChanged.connect(self._profile_changed)
        self.profile.message.connect(self._toast)
        self.schedule.startRequested.connect(self._start)
        self.schedule.resumeRequested.connect(self._resume)
        self.schedule.scheduleChanged.connect(self.dashboard.refresh)
        self.active.sessionChanged.connect(self._data_changed)
        self.history.historyChanged.connect(self._data_changed)
        self.dashboard.navigate.connect(self.show_page)
        self.dashboard.startRequested.connect(self._start)
        self.dashboard.resumeRequested.connect(self._resume)
        self.dashboard.skillLink.connect(self._open_skill)

        self.details.rank_provider = self._skill_rank_lines
        self.details.achievement_provider = self._skill_achievement_lines
        self.xp.subscribe(self._xp_changed)
        self.settings.subscribe(lambda cfg: self.apply_settings())
        self.ranks.subscribe(self._refresh_rank_views)
        self.apply_settings()

        self._refresh()
        self._update_active_label()
        self._startup_xp = self.xp.sync()      # credits real activity from before the XP system existed, once
        self._sync_cosmetics()
        if self.sess.active():
            self.statusBar().showMessage("You have an unfinished workout. Open Active Workout to resume it.", 10000)
        self._start_welcome_if_needed()

    # ------------------------------------------------------------- welcome
    def _start_welcome_if_needed(self):
        """First run: ask for a name and an avatar before anything else."""
        if not self.profiles.needs_welcome():
            return
        self.welcome = WelcomePage()
        self.welcome.confirmed.connect(self._on_welcome)
        self.stack.insertWidget(0, self.welcome)
        self.stack.setCurrentWidget(self.welcome)
        self.header.setVisible(False)
        self.statusBar().setVisible(False)
        QTimer.singleShot(0, self.welcome.focus_name)

    def _on_welcome(self, name, avatar):
        """The player confirmed their identity: store it and enter the app."""
        self.profiles.create(name, avatar)
        self.profiles.mark_welcome_seen()
        if hasattr(self, "welcome"):
            idx = self.stack.indexOf(self.welcome)
            if idx >= 0:
                self.stack.removeWidget(self.welcome)
            self.welcome.setParent(None)
            self.welcome.deleteLater()
            del self.welcome
        self.header.setVisible(True)
        self.statusBar().setVisible(True)
        self.profile.refresh()
        self.audio.sfx("success")
        self._toast(f"Welcome, {name}!")
        self.show_page("dashboard")

    # --------------------------------------------------------------- UI build
    def _build_header(self):
        bar = QWidget()
        bar.setObjectName("topbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 4, 16, 0)
        row.setSpacing(2)
        brand = QVBoxLayout()
        brand.setSpacing(0)
        t = QLabel("CALIX")
        t.setObjectName("brand")
        s = QLabel("CALISTHENICS PROGRESSION")
        s.setObjectName("brandSub")
        brand.addWidget(t)
        brand.addWidget(s)
        row.addLayout(brand)
        row.addSpacing(24)
        group = QButtonGroup(self)
        self.nav = {}
        for key, label in PAGES:
            b = QPushButton(label)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            group.addButton(b)
            row.addWidget(b)
            self.nav[key] = b
        row.addStretch(1)
        self.nav["tree"].setChecked(True)
        return bar

    def _build_tree_toolbar(self):
        bar = QWidget()
        bar.setObjectName("subbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 8, 16, 8)
        row.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search skills…  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(240)
        comp = QCompleter(sorted(s.name for s in SKILLS), self)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        comp.activated[str].connect(self._on_completer)
        self.search.setCompleter(comp)
        self.search.textChanged.connect(self._apply_filters)
        self.search.returnPressed.connect(self._go_first_match)

        self.cat_combo = QComboBox()
        self.cat_combo.addItem("All categories", None)
        for key, (label, _) in CATEGORIES.items():
            self.cat_combo.addItem(label, key)
        self.tier_combo = QComboBox()
        self.tier_combo.addItem("All levels", None)
        for i, name in enumerate(TIERS):
            self.tier_combo.addItem(name, i)
        self.status_combo = QComboBox()
        self.status_combo.addItem("Any status", None)
        for key, label in STATUS_LABELS.items():
            self.status_combo.addItem(label, key)
        for c in (self.cat_combo, self.tier_combo, self.status_combo):
            c.currentIndexChanged.connect(self._apply_filters)

        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear_filters)

        row.addWidget(self.search, 1)
        row.addWidget(self.cat_combo)
        row.addWidget(self.tier_combo)
        row.addWidget(self.status_combo)
        row.addWidget(clear)
        row.addSpacing(12)

        for text, fn, tip in (("−", lambda: self.view.zoom_by(1 / 1.25), "Zoom out"),
                              ("+", lambda: self.view.zoom_by(1.25), "Zoom in"),
                              ("Fit", self.view.fit_all, "Fit the whole tree")):
            b = QPushButton(text)
            b.setObjectName("tool")
            b.setToolTip(tip)
            b.clicked.connect(fn)
            row.addWidget(b)
        return bar

    def _build_menus(self):
        mb = self.menuBar()
        f = mb.addMenu("&File")
        self._act(f, "Export skill progress…", self._export)
        self._act(f, "Import skill progress…", self._import)
        f.addSeparator()
        self._act(f, "Reset skill progress…", self._reset)
        self._act(f, "Clear workout history…", self._clear_history)
        f.addSeparator()
        self._act(f, "Quit", self.close, QKeySequence.Quit)

        v = mb.addMenu("&View")
        for i, (key, label) in enumerate(PAGES, start=1):
            self._act(v, label, lambda k=key: self.show_page(k), f"Alt+{i}")
        v.addSeparator()
        self._act(v, "Fit whole tree", self.view.fit_all, "Ctrl+0")
        self._act(v, "Zoom in", lambda: self.view.zoom_by(1.25), "Ctrl+=")
        self._act(v, "Zoom out", lambda: self.view.zoom_by(1 / 1.25), "Ctrl+-")
        self._act(v, "Reset zoom", self.view.initial_view, "Ctrl+1")
        v.addSeparator()
        self.act_mute = self._act(v, "Mute all sound", self._toggle_mute, "Ctrl+M")
        self.act_mute.setCheckable(True)
        v.addSeparator()
        self._act(v, "Toggle sidebar", lambda: self.tabs.setVisible(not self.tabs.isVisible()), "F4")
        self._act(v, "Focus search", lambda: (self.search.setFocus(), self.search.selectAll()), "Ctrl+F")

        h = mb.addMenu("&Help")
        self._act(h, "How it works", lambda: QMessageBox.information(self, "How it works", HELP_TEXT))
        self._act(h, "About", lambda: QMessageBox.about(
            self, "About",
            f"<b>CALIX – Calisthenics Skill Tree</b><br>{len(SKILLS)} skills across {len(CATEGORIES)} branches "
            f"and {len(EXERCISES)} exercises in the library.<br>"
            f"Everything is stored locally at:<br><small>{self.store.path}</small>"))

    def _act(self, menu, text, fn, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(lambda _=False: fn())
        menu.addAction(a)
        self.addAction(a)
        return a

    # --------------------------------------------------------------- navigation
    def show_page(self, key):
        self.stack.setCurrentWidget(self.pages[key])
        self.nav[key].setChecked(True)
        self.zoom_label.setVisible(key == "tree")
        self.count_label.setVisible(key == "tree")
        page = self.pages[key]
        if hasattr(page, "refresh") and key != "tree":
            page.refresh()

    def _update_active_label(self):
        self.nav["active"].setText("● Active Workout" if self.sess.active() else "Active Workout")

    def _start(self, workout_id, entry_id=None):
        if self.active.start_workout(workout_id, entry_id):
            self.show_page("active")

    def _resume(self):
        self.active.resume()
        self.show_page("active")

    def _open_skill(self, sid):
        self.show_page("tree")
        self.goto(sid)

    def _workouts_changed(self):
        self.schedule.refresh()
        self.active.refresh()
        self.dashboard.refresh()

    # -------------------------------------------------------- library links
    def _toast(self, text):
        self.statusBar().showMessage(text, 5000)

    def _add_to_workout(self, ex_id):
        """The Library sent an exercise to the Workout Builder."""
        if self.builder.add_exercise(ex_id):
            ex = self.wrepo.exercise(ex_id)
            self.audio.sfx("toggle")
            self.show_page("builder")
            self._toast(f"{ex['name']} added to the workout - don't forget to save it")

    def _open_in_library(self, ex_id):
        """The Builder wants to show an exercise in the full library."""
        self.show_page("library")
        self.library.select_exercise(ex_id)

    def _profile_changed(self):
        """The player changed the name, the avatar or a cosmetic."""
        self.profile.refresh()
        self.library.refresh()

    def _sync_cosmetics(self):
        """Unlock the cosmetic rewards whose condition is now met."""
        try:
            level = self.xp.level().level
            ach_ids = {r["a"].id for r in self.xp.achievement_rows() if r["unlocked"]}
            new = self.profiles.sync_cosmetics(level, ach_ids)
        except Exception:
            return []
        if new:
            names = ", ".join(c["name"] for c in new)
            self._toast(f"New cosmetic unlocked: {names}")
            if hasattr(self, "profile"):
                self.profile.refresh()
        return new

    # ---------------------------------------------------- settings and ranks
    def _pattern_path(self):
        """Tiny tile used by the 'subtle pattern' background (generated once, stored next to the database)."""
        path = self.store.path.parent / "pattern_tile.png"
        if not path.exists():
            pm = QPixmap(28, 28)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setPen(QPen(QColor(255, 255, 255, 30), 2))
            p.drawPoint(14, 14)
            p.setPen(QPen(QColor(255, 255, 255, 9), 1))
            p.drawLine(0, 28, 28, 0)
            p.end()
            pm.save(str(path))
        return path.as_posix()

    def apply_settings(self):
        """Restyle the whole application from the current settings, instantly."""
        cfg = self.settings.all()
        app = QApplication.instance()
        font = app.font()
        font.setPointSize(cfg["font_size"])
        app.setFont(font)
        app.setStyleSheet(build_qss(cfg, self._pattern_path() if cfg["bg"] == "pattern" else None))
        self.view.apply_settings(cfg)
        self.history.bars.set_color(cfg["accent"])
        set_animations(cfg["animations"])
        self.audio.apply()
        if hasattr(self, "act_mute"):
            self.act_mute.setChecked(not (cfg["sfx"] or cfg["music"]))

    def _skill_rank_lines(self, skill_id):
        return [f"{rank_html(r.rank)} &nbsp;{r.track.name}: <span style='color:#8b95a7'>{r.headline} · next: {r.goal}</span>"
                for r in self.ranks.results_for_skill(skill_id)]

    def _summary_text(self, done):
        lv = self.xp.level()
        return f"{done}/{len(SKILLS)} skills completed · Level {lv.level} {lv.title} · {lv.total:,} XP"

    def _sync_and_announce(self):
        """Credit anything new that the user just recorded and show it (XP, achievements, level-up)."""
        res = self.xp.sync()
        if res.leveled_up:
            self.audio.sfx("levelup")
        elif res.unlocked:
            self.audio.sfx("achievement")
        elif res.awards:
            self.audio.sfx("success")
        announce_progress(self, res)
        self._sync_cosmetics()

    def _xp_changed(self):
        """XP or achievements changed: refresh every view that shows them."""
        if not hasattr(self, "achievements_page"):
            return
        progress = self.store.progress()
        self.achievements_page.refresh()
        self.dashboard.refresh()
        self.stats.refresh(progress)
        done = sum(1 for sid in self.graph.order if self.graph.status(sid, progress) == "completed")
        self.stats_summary = self._summary_text(done)
        if not self._filters_active():
            self.count_label.setText(self.stats_summary)

    def _skill_achievement_lines(self, skill_id):
        out = []
        for r in self.xp.achievements_for_skill(skill_id):
            a = r["a"]
            color = AC.RARITIES[a.rarity][1]
            state = (f"<span style='color:#69db7c'>✓ unlocked {r['unlocked']}</span>" if r["unlocked"] else
                     f"<span style='color:#8b95a7'>{r['progress']:g}/{a.target:g} {a.unit} · +{a.xp} XP</span>")
            out.append(f"<span style='color:{color}'>{a.icon} <b>{a.name}</b></span> {state}")
        return out

    def _refresh_rank_views(self):
        """Ranks changed (new performance, record, skill completed, history deleted): update every rank view."""
        if not hasattr(self, "rank_page"):
            return
        self.view.set_rank_badges(self.ranks.skill_ranks())
        self.details.set_progress(self.store.progress())
        self.rank_page.refresh()
        self.dashboard.refresh()
        self.builder.refresh_ranks()
        self.library.refresh()
        if hasattr(self, "profile"):
            self.profile.refresh()

    def _data_changed(self):
        """A session was started/finished/discarded or history was edited."""
        self._update_active_label()
        self.schedule.refresh()
        self.history.refresh()
        self.dashboard.refresh()
        self._refresh()                 # finished sets can add skill-tree records
        self._sync_and_announce()       # nothing new if the Active Workout page already credited it

    def _clear_history(self):
        if QMessageBox.warning(self, "Clear workout history",
                               "Delete ALL completed workout sessions? Your workouts, schedule and skill "
                               "progress are kept. This cannot be undone.",
                               QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.sess.delete_all_history()
            self._data_changed()
            self.statusBar().showMessage("Workout history cleared", 5000)

    def closeEvent(self, e):
        self.active.persist()           # keep an in-progress session resumable
        self.audio.close()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self._click_sfx)
        super().closeEvent(e)

    def _toggle_mute(self):
        """Ctrl+M: silence everything, or bring it all back."""
        mute = self.settings.get("sfx") or self.settings.get("music")
        self.settings.set("sfx", not mute)
        self.settings.set("music", not mute)
        self.statusBar().showMessage("Sound muted" if mute else "Sound on", 3000)

    # --------------------------------------------------------------- behaviour
    def showEvent(self, e):
        super().showEvent(e)
        if not self._shown:
            self._shown = True
            QTimer.singleShot(0, self.view.initial_view)
            if not self._startup_xp.empty:     # e.g. first launch after the upgrade credits earlier real activity
                QTimer.singleShot(300, lambda: announce_progress(self, self._startup_xp))

    def goto(self, sid):
        """Select a skill, show its details and pan to it."""
        self.view.select(sid)
        self.details.show_skill(sid, self.store.progress())
        self.tabs.setCurrentWidget(self.details)
        self.view.focus(sid)

    def _on_node_clicked(self, sid):
        self.view.select(sid)
        self.details.show_skill(sid, self.store.progress())
        self.tabs.setCurrentWidget(self.details)

    def _on_status(self, sid, status):
        self.store.set_status(sid, status)
        self._refresh()
        self._sync_and_announce()

    def _on_record(self, sid, value):
        self.store.add_record(sid, value)
        self._refresh()
        self._sync_and_announce()

    def _refresh(self):
        progress = self.store.progress()
        self.view.refresh(progress)
        self.details.set_progress(progress)
        self.stats.refresh(progress)
        self._apply_filters()
        done = sum(1 for sid in self.graph.order if self.graph.status(sid, progress) == "completed")
        self.stats_summary = self._summary_text(done)
        self._refresh_rank_views()
        if not self._filters_active():
            self.count_label.setText(self.stats_summary)

    # ------------------------------------------------------------- filtering
    def _filters_active(self):
        return bool(self.search.text().strip()) or any(
            c.currentData() is not None for c in (self.cat_combo, self.tier_combo, self.status_combo))

    def _apply_filters(self, *_):
        if not hasattr(self, "view") or not hasattr(self, "status_combo"):
            return []
        matches = self.view.apply_filter(self.search.text(), self.cat_combo.currentData(),
                                         self.tier_combo.currentData(), self.status_combo.currentData())
        if self._filters_active():
            self.count_label.setText(f"{len(matches)} matching skill{'s' if len(matches) != 1 else ''}")
        else:
            self.count_label.setText(getattr(self, "stats_summary", ""))
        return matches

    def _clear_filters(self):
        self.search.clear()
        for c in (self.cat_combo, self.tier_combo, self.status_combo):
            c.setCurrentIndex(0)

    def _go_first_match(self):
        matches = self._apply_filters()
        if matches and self._filters_active():
            self.goto(matches[0])

    def _on_completer(self, name):
        for s in SKILLS:
            if s.name == name:
                self.goto(s.id)
                break

    # ------------------------------------------------------------ file menu
    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export progress", "skilltree_progress.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.store.export_data(), fh, indent=2)
            self.statusBar().showMessage(f"Exported to {path}", 5000)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import progress", "", "JSON (*.json)")
        if not path:
            return
        if QMessageBox.question(self, "Import progress",
                                "This replaces your current progress and records. Continue?") != QMessageBox.Yes:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            n = self.store.import_data(data, set(self.graph.skills))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            QMessageBox.critical(self, "Import failed", f"Could not read that file:\n{exc}")
            return
        self._refresh()
        self._sync_and_announce()
        self.statusBar().showMessage(f"Imported {n} skill statuses", 5000)

    def _reset(self):
        if QMessageBox.warning(self, "Reset progress",
                               "Delete ALL skill progress and personal records? This cannot be undone.",
                               QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.store.reset()
            self._refresh()
            self.statusBar().showMessage("Progress reset", 5000)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CALIX")
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(["Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue", "Ubuntu", "Arial"])
    font.setPointSize(10)
    app.setFont(font)
    win = MainWindow()
    win.resize(1500, 920)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
