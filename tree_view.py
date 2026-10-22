"""The interactive skill tree: QGraphicsView + custom node/edge items."""
import math

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QPointF, QRectF, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPolygonF)
from PySide6.QtWidgets import (QFrame, QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem,
                               QGraphicsSimpleTextItem, QGraphicsScene, QGraphicsView)

from graph import NODE_H as H, NODE_W as W
from ranks import RANKS
from skills_data import CATEGORIES, TIERS

ORANGE = "#ffa94d"


def blend(a, b, t):
    """Mix colour a into b by factor t (0..1)."""
    a, b = QColor(a), QColor(b)
    return QColor(int(a.red() * t + b.red() * (1 - t)),
                  int(a.green() * t + b.green() * (1 - t)),
                  int(a.blue() * t + b.blue() * (1 - t)))


class NodeItem(QGraphicsItem):
    def __init__(self, skill, view):
        super().__init__()
        self.skill = skill
        self.view = view
        self.cat_color = QColor(CATEGORIES[skill.category][1])
        self.color = QColor(self.cat_color)        # node colour (settings may override)
        self.glow_color = QColor(self.color)       # highlight of skills available to train
        self.rank = 0
        self.status = "locked"
        self.selected_flag = False
        self.hovered = False
        self.dim = False
        self.flash = 0.0
        self.setZValue(10)
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setToolTip(f"{skill.name}\n{TIERS[skill.tier]} · {CATEGORIES[skill.category][0]}\nClick for details")

    def boundingRect(self):
        return QRectF(-W / 2 - 14, -H / 2 - 14, W + 28, H + 28)

    def shape(self):
        path = QPainterPath()
        path.addRoundedRect(QRectF(-W / 2, -H / 2, W, H), 12, 12)
        return path

    def hoverEnterEvent(self, e):
        self.hovered = True
        self.view.set_hover(self.skill.id)
        self.update()

    def hoverLeaveEvent(self, e):
        self.hovered = False
        self.view.set_hover(None)
        self.update()

    # ----------------------------------------------------------------- paint
    def paint(self, p, option, widget=None):
        p.setRenderHint(QPainter.Antialiasing, True)
        st, c = self.status, self.color
        pulse = 0.5 + 0.5 * math.sin(self.view.phase * 2.0)
        rect = QRectF(-W / 2, -H / 2, W, H)
        if self.dim:
            p.setOpacity(0.2)

        # glow
        glow, alpha = None, 0
        if st == "available":
            glow, alpha = self.glow_color, 28 + 55 * pulse
        elif st == "training":
            glow, alpha = QColor(ORANGE), 35 + 60 * pulse
        elif st == "completed":
            glow, alpha = c, 30
        if self.selected_flag:
            glow, alpha = QColor("#ffffff"), 80
        elif self.hovered:
            glow, alpha = QColor("#ffffff"), 45
        if glow is not None and self.view.effects:
            for width, k in ((16, 0.35), (10, 0.6), (5, 1.0)):
                g = QColor(glow)
                g.setAlpha(int(alpha * k))
                p.setPen(QPen(g, width))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(rect, 12, 12)

        # body colours per state
        if st == "locked":
            top, bot, border, txt = QColor("#171c26"), QColor("#11151d"), QColor("#2b3341"), QColor("#6b7686")
        elif st == "available":
            top, bot, border, txt = QColor("#1f2838"), QColor("#161d2a"), QColor(self.glow_color), QColor("#eef2f8")
        elif st == "training":
            top, bot = blend(ORANGE, "#141a24", 0.25), blend(ORANGE, "#141a24", 0.10)
            border, txt = QColor(ORANGE), QColor("#fff4e6")
        else:
            top, bot = blend(c, "#10141b", 0.5), blend(c, "#10141b", 0.28)
            border, txt = c.lighter(115), QColor("#ffffff")

        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0, top)
        grad.setColorAt(1, bot)
        p.setBrush(QBrush(grad))
        p.setPen(QPen(border, 1.4 if st == "locked" else 2.4))
        p.drawRoundedRect(rect, 12, 12)

        if not self.view.effects and (self.selected_flag or self.hovered):
            p.setPen(QPen(QColor("#ffffff"), 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, 12, 12)

        # category accent bar
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2b3341") if st == "locked" else c)
        p.drawRoundedRect(QRectF(-W / 2 + 7, -H / 2 + 11, 4, H - 22), 2, 2)

        # name
        font = QFont(self.view.font())
        font.setPointSizeF(9.5)
        font.setBold(True)
        p.setFont(font)
        p.setPen(txt)
        p.drawText(QRectF(-W / 2 + 19, -H / 2 + 6, W - 52, H - 26),
                   int(Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap), self.skill.name)

        # tier pips (4 slots)
        for i in range(4):
            cx, cy = -W / 2 + 21 + i * 10, H / 2 - 12
            filled = i <= self.skill.tier
            p.setPen(Qt.NoPen if filled else QPen(QColor("#2b3341"), 1))
            p.setBrush(QColor("#3a4454") if (filled and st == "locked") else (c if filled else Qt.NoBrush))
            p.drawEllipse(QPointF(cx, cy), 3, 3)

        self._status_icon(p, QPointF(W / 2 - 17, -H / 2 + 17), pulse)

        if self.rank > 0 and self.view.show_rank:
            self._rank_badge(p)

        if self.flash > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, int(150 * self.flash)))
            p.drawRoundedRect(rect, 12, 12)

    def _rank_badge(self, p):
        """Small hexagon with the rank numeral at the bottom-right of the node."""
        cx, cy, r = W / 2 - 18, H / 2 - 14, 9.5
        col = QColor(RANKS[self.rank][1])
        hexa = QPolygonF([QPointF(cx + r * math.cos(math.radians(90 + 60 * i)),
                                  cy - r * math.sin(math.radians(90 + 60 * i))) for i in range(6)])
        p.setPen(QPen(col.lighter(130), 1.4))
        p.setBrush(blend(col, "#10141b", 0.75))
        p.drawPolygon(hexa)
        f = QFont(self.view.font())
        f.setPointSizeF(6.5)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(cx - r, cy - r, 2 * r, 2 * r), int(Qt.AlignCenter), str(self.rank))

    def _status_icon(self, p, ctr, pulse):
        st = self.status
        x, y = ctr.x(), ctr.y()
        if st == "completed":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#69db7c"))
            p.drawEllipse(ctr, 9, 9)
            pen = QPen(QColor("#0b1a10"), 2.2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPolyline(QPolygonF([QPointF(x - 4, y), QPointF(x - 1, y + 3.5), QPointF(x + 4.5, y - 3.5)]))
        elif st == "locked":
            col = QColor("#6b7686")
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x - 5.5, y - 1, 11, 8.5), 2, 2)
            pen = QPen(col, 1.8)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(x - 3.5, y - 6.5, 7, 9), 0, 180 * 16)
        elif st == "training":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(ORANGE))
            p.drawPolygon(QPolygonF([QPointF(x - 4, y - 6), QPointF(x - 4, y + 6), QPointF(x + 6, y)]))
        else:  # available
            col = QColor(self.glow_color)
            col.setAlpha(int(140 + 115 * pulse))
            p.setPen(QPen(col, 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(ctr, 5 + pulse, 5 + pulse)


class EdgeItem(QGraphicsPathItem):
    def __init__(self, parent_node, child_node):
        super().__init__()
        self.parent_id = parent_node.skill.id
        self.child_id = child_node.skill.id
        self.cat_color = QColor(parent_node.cat_color)
        self.color = QColor(self.cat_color)
        self.kind = "idle"
        a = QPointF(parent_node.x(), parent_node.y() + H / 2)
        b = QPointF(child_node.x(), child_node.y() - H / 2)
        mid = (a.y() + b.y()) / 2
        path = QPainterPath(a)
        path.cubicTo(QPointF(a.x(), mid), QPointF(b.x(), mid), b)
        self.setPath(path)
        self.setZValue(1)

    def apply(self, kind, highlight, dim):
        self.kind = kind
        if kind == "idle":
            col, width, alpha = QColor("#2a3242"), 1.8, 255
        elif kind == "done":
            col, width, alpha = QColor(self.color), 2.8, 230
        else:
            col, width, alpha = QColor(self.color), 2.4, 200
        if highlight:
            width += 1.4
            col = QColor("#6f7f9c") if kind == "idle" else col.lighter(125)
            alpha = 255
        col.setAlpha(int(alpha * (0.2 if dim else 1)))
        pen = QPen(col, width)
        pen.setCapStyle(Qt.RoundCap)
        if kind == "active":
            pen.setDashPattern([2.5, 3.5])
        self.setPen(pen)

    def animate(self, phase):
        pen = self.pen()
        pen.setDashOffset(-phase * 3)
        self.setPen(pen)


class TreeView(QGraphicsView):
    skillClicked = Signal(str)
    zoomChanged = Signal(float)

    MIN_ZOOM, MAX_ZOOM = 0.12, 2.6

    def __init__(self, graph, parent=None):
        super().__init__(parent)
        self.graph = graph
        self.phase = 0.0
        self.nodes, self.edges, self.active_edges = {}, [], []
        self.selected = self.hover = None
        self._press = self._last = None
        self._moved = False
        self._ready = False
        self._anim = None
        self.progress = {}
        self.animations = self.effects = self.show_rank = self.show_grid = True
        self.pattern = False
        self.bg = ("#0b0e14", "#0d121c")

        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.viewport().setMouseTracking(True)

        self._build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    # ----------------------------------------------------------------- build
    def _build(self):
        sc = self.scene()
        pos, lanes, max_row = self.graph.layout()

        for cat, (left, width) in lanes.items():
            label, color = CATEGORIES[cat]
            band = QGraphicsRectItem(QRectF(left - 10, -130, width + 20, max_row * 150 + 250))
            grad = QLinearGradient(0, -130, 0, max_row * 150 + 120)
            top = QColor(color)
            top.setAlpha(34)
            bottom = QColor(color)
            bottom.setAlpha(4)
            grad.setColorAt(0, top)
            grad.setColorAt(1, bottom)
            band.setBrush(QBrush(grad))
            band.setPen(QPen(Qt.NoPen))
            band.setZValue(-5)
            sc.addItem(band)
            title = QGraphicsSimpleTextItem(label.upper())
            f = QFont(self.font())
            f.setPointSizeF(17)
            f.setBold(True)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 4)
            title.setFont(f)
            title.setBrush(QColor(color))
            title.setPos(left + 14, -112)
            title.setZValue(-4)
            sc.addItem(title)

        for sid in self.graph.order:
            n = NodeItem(self.graph.skills[sid], self)
            n.setPos(*pos[sid])
            sc.addItem(n)
            self.nodes[sid] = n

        for sid in self.graph.order:
            for p in self.graph.skills[sid].prereqs:
                e = EdgeItem(self.nodes[p], self.nodes[sid])
                sc.addItem(e)
                self.edges.append(e)

        self.content_rect = sc.itemsBoundingRect()
        sc.setSceneRect(self.content_rect.adjusted(-600, -400, 600, 400))

    # ----------------------------------------------------------------- state
    def refresh(self, progress):
        self.progress = progress
        for sid, n in self.nodes.items():
            new = self.graph.status(sid, progress)
            if self._ready and self.animations and new != n.status and new in ("available", "completed"):
                n.flash = 1.0
            n.status = new
        self._ready = True
        self._restyle()
        for n in self.nodes.values():
            n.update()

    def _restyle(self):
        focus = self.hover or self.selected
        hi = set()
        if focus:
            for sid in self.graph.ancestors(focus) | {focus}:
                for p in self.graph.skills[sid].prereqs:
                    hi.add((p, sid))
            for c in self.graph.children.get(focus, []):
                hi.add((focus, c))
        for e in self.edges:
            pn, cn = self.nodes[e.parent_id], self.nodes[e.child_id]
            if pn.status == "completed" and cn.status == "completed":
                kind = "done"
            elif pn.status == "completed":
                kind = "active"
            else:
                kind = "idle"
            e.apply(kind, (e.parent_id, e.child_id) in hi, pn.dim or cn.dim)
        self.active_edges = [e for e in self.edges if e.kind == "active"]

    def select(self, sid):
        self.selected = sid
        for k, n in self.nodes.items():
            n.selected_flag = (k == sid)
            n.update()
        self._restyle()

    def set_hover(self, sid):
        self.hover = sid
        self._restyle()

    def apply_filter(self, text="", category=None, tier=None, status=None):
        """Dim nodes that don't match. Returns the matching ids in tree order."""
        t = text.strip().lower()
        matches = []
        for sid in self.graph.order:
            n = self.nodes[sid]
            s = n.skill
            ok = ((not t or t in s.name.lower() or t in CATEGORIES[s.category][0].lower())
                  and (category is None or s.category == category)
                  and (tier is None or s.tier == tier)
                  and (status is None or n.status == status))
            n.dim = not ok
            if ok:
                matches.append(sid)
            n.update()
        self._restyle()
        return matches

    # ------------------------------------------------------------- animation
    def _tick(self):
        if not self.isVisible() or not self.animations:
            return
        self.phase += 0.09
        for n in self.nodes.values():
            if n.flash > 0:
                n.flash = max(0.0, n.flash - 0.035)
                n.update()
            elif n.status in ("available", "training"):
                n.update()
        for e in self.active_edges:
            e.animate(self.phase)

    # ----------------------------------------------------------- navigation
    def zoom_by(self, factor):
        cur = self.transform().m11()
        new = max(self.MIN_ZOOM, min(self.MAX_ZOOM, cur * factor))
        f = new / cur
        if abs(f - 1) > 1e-6:
            self.scale(f, f)
        self.zoomChanged.emit(self.transform().m11())

    def set_zoom(self, z):
        self.resetTransform()
        self.scale(z, z)
        self.zoomChanged.emit(z)

    def fit_all(self):
        self.fitInView(self.content_rect.adjusted(-40, -60, 40, 40), Qt.KeepAspectRatio)
        self.zoomChanged.emit(self.transform().m11())

    def initial_view(self):
        vw = max(1, self.viewport().width())
        z = max(0.35, min(0.85, vw / self.content_rect.width()))
        self.set_zoom(z)
        cx = self.content_rect.center().x()
        top = self.content_rect.top()
        self.centerOn(cx, top + (self.viewport().height() / 2) / z - 40)

    def focus(self, sid):
        """Smoothly pan to a node."""
        if sid not in self.nodes:
            return
        if self.transform().m11() < 0.6:
            self.set_zoom(0.85)
        if not self.animations:
            self.centerOn(self.nodes[sid].pos())
            return
        anim = QVariantAnimation(self)
        anim.setDuration(450)
        anim.setStartValue(self.mapToScene(self.viewport().rect().center()))
        anim.setEndValue(self.nodes[sid].pos())
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        anim.valueChanged.connect(lambda v: self.centerOn(v))
        anim.start(QAbstractAnimation.DeleteWhenStopped)
        self._anim = anim

    # ---------------------------------------------------------------- events
    def wheelEvent(self, e):
        dy = e.angleDelta().y()
        if dy:
            self.zoom_by(1.0012 ** dy)
        e.accept()

    def mousePressEvent(self, e):
        if e.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._press = self._last = e.position().toPoint()
            self._moved = False
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._press is not None:
            pos = e.position().toPoint()
            if not self._moved and (pos - self._press).manhattanLength() > 5:
                self._moved = True
                self.viewport().setCursor(Qt.ClosedHandCursor)
            if self._moved:
                d = pos - self._last
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())
            self._last = pos
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._press is not None:
            if not self._moved and e.button() == Qt.LeftButton:
                for it in self.items(e.position().toPoint()):
                    if isinstance(it, NodeItem):
                        self.skillClicked.emit(it.skill.id)
                        break
            self._press = None
            self.viewport().unsetCursor()
            e.accept()
        else:
            super().mouseReleaseEvent(e)

    def drawBackground(self, p, rect):
        grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        grad.setColorAt(0, QColor(self.bg[0]))
        grad.setColorAt(1, QColor(self.bg[1]))
        p.fillRect(rect, QBrush(grad))
        if self.show_grid and self.transform().m11() >= 0.35:
            step = 26 if self.pattern else 40
            p.setPen(QPen(QColor(255, 255, 255, 30 if self.pattern else 16), 2))
            x0 = int(rect.left()) - int(rect.left()) % step
            y0 = int(rect.top()) - int(rect.top()) % step
            y = y0
            while y < rect.bottom():
                x = x0
                while x < rect.right():
                    p.drawPoint(QPointF(x, y))
                    x += step
                y += step

    # -------------------------------------------------------------- settings
    def apply_settings(self, cfg):
        """Apply appearance settings immediately (colours, animations, effects, badges, grid)."""
        from theme import canvas_colors
        self.animations, self.effects = cfg["animations"], cfg["effects"]
        self.show_rank, self.show_grid = cfg["rank_badges"], cfg["tree_grid"]
        self.pattern, self.bg = cfg["bg"] == "pattern", canvas_colors(cfg)
        node_c = cfg["tree_node_color"] if cfg["tree_node_mode"] == "custom" else None
        edge_c = cfg["tree_edge_color"] if cfg["tree_edge_mode"] == "custom" else None
        unlock = cfg["tree_unlock_color"] if cfg["tree_unlock_mode"] == "custom" else None
        for n in self.nodes.values():
            n.color = QColor(node_c) if node_c else QColor(n.cat_color)
            n.glow_color = QColor(unlock) if unlock else QColor(n.color)
        for e in self.edges:
            e.color = QColor(edge_c) if edge_c else QColor(e.cat_color)
        if self.animations:
            if not self.timer.isActive():
                self.timer.start(33)
        else:
            self.timer.stop()
            self.phase = 0.0
            for n in self.nodes.values():
                n.flash = 0.0
        self._restyle()
        for n in self.nodes.values():
            n.update()
        self.viewport().update()

    def set_rank_badges(self, ranks):
        """ranks: {skill id: rank index}"""
        for sid, n in self.nodes.items():
            n.rank = ranks.get(sid, 0)
            n.update()
