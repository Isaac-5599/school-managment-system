"""Generate the report figures (ERD, DFDs, use-case diagram) as SVG files.

    python3 docs/make_diagrams.py

Everything is positioned explicitly, so a figure can be nudged by editing the
coordinate tables below and re-running the script.
"""

import os
import xml.sax.saxutils as sax

FONT = "Helvetica, Arial, sans-serif"
NAVY = "#1e2a52"
INK = "#0f172a"
LINE = "#64748b"
ENTITY_HEAD = "#dbeafe"
PROCESS_FILL = "#fef3c7"
PROCESS_STROKE = "#b45309"
STORE_FILL = "#f1f5f9"
ACTOR_STROKE = "#334155"
USECASE_FILL = "#ecfdf5"
USECASE_STROKE = "#047857"

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def esc(text):
    return sax.escape(str(text))


class Svg:
    def __init__(self, width, height, title):
        self.w = width
        self.h = height
        self.parts = [
            "<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' "
            "viewBox='0 0 %d %d' role='img' font-family='%s'>"
            % (width, height, width, height, esc(FONT)),
            "<title>%s</title>" % esc(title),
            "<defs><marker id='arrow' viewBox='0 0 10 10' refX='9' refY='5' "
            "markerWidth='7' markerHeight='7' orient='auto-start-reverse'>"
            "<path d='M0,0 L10,5 L0,10 z' fill='%s'/></marker></defs>" % LINE,
            "<rect width='100%' height='100%' fill='white'/>",
        ]

    def rect(self, x, y, w, h, fill="#ffffff", stroke="#94a3b8", rx=8, sw=1.4, dash=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        self.parts.append(
            "<rect x='%g' y='%g' width='%g' height='%g' rx='%g' fill='%s' "
            "stroke='%s' stroke-width='%g'%s/>" % (x, y, w, h, rx, fill, stroke, sw, d)
        )

    def text(self, x, y, s, size=12.5, fill=INK, anchor="start", weight="normal", style=""):
        extra = ' %s' % style if style else ""
        self.parts.append(
            "<text x='%g' y='%g' font-size='%g' fill='%s' text-anchor='%s' "
            "font-weight='%s'%s>%s</text>"
            % (x, y, size, fill, anchor, weight, extra, esc(s))
        )

    def path(self, pts, dash=None, width=1.4, arrow=True, color=LINE):
        d = " ".join(("M" if i == 0 else "L") + "%g,%g" % p for i, p in enumerate(pts))
        dd = ' stroke-dasharray="%s"' % dash if dash else ""
        ah = " marker-end='url(#arrow)'" if arrow else ""
        self.parts.append(
            "<path d='%s' fill='none' stroke='%s' stroke-width='%g'%s%s/>"
            % (d, color, width, dd, ah)
        )

    def line(self, p1, p2, **kw):
        self.path([p1, p2], **kw)

    def label(self, x, y, s, size=11.5, anchor="middle", fill="#475569", weight="normal"):
        self.text(x, y, s, size=size, fill=fill, anchor=anchor, weight=weight,
                  style="stroke='white' stroke-width='4' paint-order='stroke'")

    def caption(self, text_, y=None):
        self.text(24, y if y is not None else self.h - 14, text_, size=12.5,
                  fill="#475569", style="font-style='italic'")

    def save(self, name):
        self.parts.append("</svg>")
        path = os.path.join(OUT_DIR, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.parts))
        return path


# --------------------------------------------------------------------------
# Figure 1: entity-relationship diagram
# --------------------------------------------------------------------------

ROW_Y = [60, 430, 800]
COL_X = [40, 400, 760, 1120, 1480]
EW = 280
HEAD_H = 34
ROW_H = 19


def entity(x, y, title, attrs):
    h = HEAD_H + 8 + ROW_H * len(attrs) + 8
    return {"x": x, "y": y, "w": EW, "h": h, "title": title, "attrs": attrs}


def anchor(e, spec):
    edge, _, frac = spec.partition(":")
    f = float(frac or 0.5)
    if edge == "t":
        return (e["x"] + f * e["w"], e["y"])
    if edge == "b":
        return (e["x"] + f * e["w"], e["y"] + e["h"])
    if edge == "l":
        return (e["x"], e["y"] + f * e["h"])
    return (e["x"] + e["w"], e["y"] + f * e["h"])


E = {}
E["users"] = entity(COL_X[0], ROW_Y[0], "users", [
    "id  PK", "full_name", "username  UQ", "email  UQ", "password_hash",
    "password_salt", "role  (admin|teacher|student)", "is_active", "created_at"])
E["teachers"] = entity(COL_X[1], ROW_Y[0], "teachers", [
    "id  PK", "staff_no  UQ", "user_id  FK -> users", "first_name", "last_name",
    "email", "phone", "qualification", "specialization", "hire_date",
    "status  (active|on leave|retired)"])
E["classes"] = entity(COL_X[2], ROW_Y[0], "classes", [
    "id  PK", "name  UQ", "level", "academic_year",
    "homeroom_teacher_id  FK -> teachers"])
E["subjects"] = entity(COL_X[3], ROW_Y[0], "subjects", [
    "id  PK", "name", "code  UQ", "category  (core|elective)"])
E["class_subjects"] = entity(COL_X[4], ROW_Y[0], "class_subjects", [
    "id  PK", "class_id  FK -> classes", "subject_id  FK -> subjects"])
E["audit_log"] = entity(COL_X[0], ROW_Y[1], "audit_log", [
    "id  PK", "user_id  FK -> users", "action", "detail", "at"])
E["students"] = entity(COL_X[1], ROW_Y[1], "students", [
    "id  PK", "admission_no  UQ", "user_id  FK -> users", "class_id  FK -> classes",
    "first_name", "last_name", "gender", "date_of_birth", "guardian_name",
    "guardian_phone", "guardian_email", "enrollment_date",
    "status  (active|graduated|withdrawn)"])
E["teacher_assignments"] = entity(COL_X[2], ROW_Y[1], "teacher_assignments", [
    "id  PK", "teacher_id  FK -> teachers", "class_id  FK -> classes",
    "subject_id  FK -> subjects"])
E["fee_invoices"] = entity(COL_X[3], ROW_Y[1], "fee_invoices", [
    "id  PK", "student_id  FK -> students", "term", "academic_year", "description",
    "amount_due", "issued_on"])
E["fee_payments"] = entity(COL_X[4], ROW_Y[1], "fee_payments", [
    "id  PK", "invoice_id  FK -> fee_invoices", "amount",
    "method  (cash|bank|mobile|cheque)", "reference", "paid_on",
    "received_by  FK -> users"])
E["attendance_records"] = entity(COL_X[0], ROW_Y[2], "attendance_records", [
    "id  PK", "class_id  FK -> classes", "student_id  FK -> students", "date",
    "period", "status  (present|absent|late|excused)", "note",
    "recorded_by  FK -> users"])
E["marks"] = entity(COL_X[1], ROW_Y[2], "marks", [
    "id  PK", "exam_id  FK -> exam_sessions", "student_id  FK -> students",
    "score  (<= exam.max_marks)", "entered_by  FK -> users", "updated_at"])
E["exam_sessions"] = entity(COL_X[2], ROW_Y[2], "exam_sessions", [
    "id  PK", "title", "term", "academic_year", "class_id  FK -> classes",
    "subject_id  FK -> subjects", "exam_date", "max_marks",
    "created_by  FK -> users"])
E["grade_scales"] = entity(COL_X[3], ROW_Y[2], "grade_scales", [
    "id  PK", "min_pct", "max_pct", "grade  (A..F)", "remark"])


def rel(src, s_edge, dst, d_edge, card_s, card_d, pts=None, name=None):
    a = anchor(E[src], s_edge)
    b = anchor(E[dst], d_edge)
    path = [a] + list(pts or []) + [b]
    return path, a, b, card_s, card_d, name


RELATIONS = [
    rel("users", "r:0.30", "teachers", "l:0.30", "0,1", "1",
        name="has login"),
    rel("users", "b:0.80", "students", "t:0.35", "0,1", "1"),
    rel("users", "b:0.35", "audit_log", "t:0.50", "1", "N"),
    rel("classes", "b:0.30", "students", "t:0.65", "1", "N", name="enrolled in"),
    rel("teachers", "r:0.30", "classes", "l:0.30", "0,1", "1", name="homeroom"),
    rel("teachers", "b:0.80", "teacher_assignments", "t:0.20", "1", "N"),
    rel("teacher_assignments", "t:0.60", "classes", "b:0.60", "N", "1"),
    rel("teacher_assignments", "r:0.20", "subjects", "b:0.20", "N", "1"),
    rel("subjects", "r:0.50", "class_subjects", "l:0.50", "1", "N"),
    rel("classes", "t:0.75", "class_subjects", "t:0.25", "1", "N",
        pts=[(970, 36), (1550, 36)]),
    rel("students", "b:0.85", "fee_invoices", "l:0.20", "1", "N",
        pts=[(638, 785), (1090, 785)]),
    rel("fee_invoices", "r:0.50", "fee_payments", "l:0.50", "1", "N"),
    rel("students", "b:0.45", "marks", "t:0.50", "1", "N",
        pts=[(532, 790)], name="scored in"),
    rel("students", "b:0.15", "attendance_records", "t:0.55", "1", "N",
        pts=[(442, 792), (194, 792)]),
    rel("classes", "b:0.10", "attendance_records", "t:0.15", "1", "N",
        pts=[(788, 210), (20, 210), (20, 830)]),
    rel("classes", "b:0.90", "exam_sessions", "t:0.40", "1", "N",
        pts=[(1060, 772), (872, 772)]),
    rel("subjects", "b:0.85", "exam_sessions", "t:0.90", "1", "N",
        pts=[(1358, 415), (1012, 415)], name="examined in"),
    rel("exam_sessions", "l:0.55", "marks", "r:0.50", "1", "N",
        pts=[(740, 922), (740, 883)]),
]


def along(p, q, dist):
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = (dx * dx + dy * dy) ** 0.5 or 1
    return (p[0] + dx / n * dist, p[1] + dy / n * dist)


def erd():
    canvas = Svg(1800, 1070, "Entity relationship diagram")
    for e in E.values():
        canvas.rect(e["x"], e["y"], e["w"], e["h"], fill="#ffffff", stroke=NAVY, rx=6, sw=1.6)
        canvas.rect(e["x"], e["y"], e["w"], HEAD_H, fill=ENTITY_HEAD, stroke=NAVY, rx=6, sw=1.6)
        canvas.text(e["x"] + 12, e["y"] + 22, e["title"], size=14.5, fill=NAVY, weight="bold")
        for i, a in enumerate(e["attrs"]):
            canvas.text(e["x"] + 12, e["y"] + HEAD_H + 8 + ROW_H * i + 14, a, size=12)
    for path, a, b, card_s, card_d, name in RELATIONS:
        canvas.path(path)
        sx, sy = along(path[0], path[1], 18)
        tx, ty = along(path[-1], path[-2], 18)
        canvas.label(sx, sy - 5, card_s, size=11, fill=NAVY, weight="bold")
        canvas.label(tx, ty - 5, card_d, size=11, fill=NAVY, weight="bold")
        if name:
            mid = path[len(path) // 2]
            canvas.label(mid[0], mid[1] - 6, name)
    canvas.text(1560, 960, "Legend", size=13, fill=NAVY, weight="bold")
    canvas.text(1560, 980, "PK primary key", size=12)
    canvas.text(1560, 998, "FK foreign key", size=12)
    canvas.text(1560, 1016, "UQ unique key", size=12)
    canvas.text(1560, 1034, "1 / N / 0,1 cardinality", size=12)
    canvas.caption(
        "users.created_by / entered_by / recorded_by / received_by all reference users(id); "
        "only the structural links are drawn. grade_scales is a lookup table read by the reporting layer.")
    return canvas.save("diagrams/figure-erd.svg")


# --------------------------------------------------------------------------
# Figure 2: context diagram (DFD level 0)
# --------------------------------------------------------------------------

def dfd_level0():
    c = Svg(1100, 640, "Context diagram (DFD level 0)")
    proc = (420, 250, 260, 130)
    c.rect(*proc, fill=PROCESS_FILL, stroke=PROCESS_STROKE, rx=14, sw=2)
    c.text(550, 305, "0", size=15, anchor="middle", fill=PROCESS_STROKE, weight="bold")
    c.text(550, 332, "School Management System", size=14, anchor="middle", weight="bold")

    def external(x, y, label):
        c.rect(x, y, 200, 52, fill="#e0f2fe", stroke="#0369a1", rx=4, sw=1.6)
        c.text(x + 100, y + 31, label, size=13.5, anchor="middle", weight="bold")

    external(40, 60, "Administrator")
    external(40, 500, "Teacher")
    external(860, 500, "Student")
    external(860, 60, "Project Supervisor")

    def flow(p1, p2):
        c.path([p1, p2])

    def lines(x, ys, texts, anchor="start", size=11.5):
        for i, t in enumerate(texts):
            c.text(x, ys + i * 16, t, size=size, anchor=anchor)

    flow((240, 86), (470, 250))
    lines(250, 58, ["login credentials", "student, staff, class and subject records"])
    flow((420, 285), (240, 108))
    lines(250, 134, ["confirmation, dashboard, audit trail"])

    flow((240, 520), (470, 380))
    lines(250, 562, ["login credentials", "daily attendance, examination scores"])
    flow((420, 350), (240, 545))
    lines(250, 480, ["class list and mark sheet"])

    flow((860, 520), (650, 375))
    lines(850, 566, ["login credentials"], anchor="end")
    flow((680, 350), (860, 540))
    lines(850, 478, ["report card and results", "attendance and fee statement"], anchor="end")

    flow((680, 285), (860, 105))
    lines(850, 138, ["project progress report"], anchor="end")

    c.caption("Level 0 presents the system as a single process and the external entities that exchange data with it.")
    return c.save("diagrams/figure-dfd-0.svg")


# --------------------------------------------------------------------------
# Figure 3: DFD level 1
# --------------------------------------------------------------------------

PROCESS_COL = lambda i: 20 + i * 155
PP_W, PP_H, PP_Y = 140, 92, 150
PROCESS_DEFS = [
    ("P1", "Authenticate &\nauthorise", "admin · teacher · student"),
    ("P2", "Manage user\naccounts", "admin"),
    ("P3", "Manage student\nrecords", "admin"),
    ("P4", "Manage teacher\nrecords", "admin"),
    ("P5", "Manage classes &\nsubjects", "admin"),
    ("P6", "Record daily\nattendance", "admin · teacher"),
    ("P7", "Enter & grade\nexam scores", "admin · teacher"),
    ("P8", "Bill fees & take\npayments", "admin"),
    ("P9", "Generate\nreports", "all roles"),
]
STORE_ROWS = [
    [("D1", "users"), ("D2", "students"), ("D3", "teachers"), ("D4", "classes"),
     ("D5", "subjects"), ("D6", "class_subjects"), ("D7", "teacher_assignments"),
     ("D8", "exam_sessions")],
    [("D9", "marks"), ("D10", "attendance_records"), ("D11", "fee_invoices"),
     ("D12", "fee_payments"), ("D13", "grade_scales"), ("D14", "audit_log")],
]
# process -> (data stores it maintains, flow label)
STORE_FLOWS = {
    "P1": (["D1"], "verify credentials"),
    "P2": (["D1", "D14"], "accounts & audit entries"),
    "P3": (["D2"], "admission record"),
    "P4": (["D3"], "staff record"),
    "P5": (["D4", "D5", "D6", "D7"], "structure & curriculum"),
    "P6": (["D10"], "attendance session"),
    "P7": (["D8", "D9"], "exam session & raw score"),
    "P8": (["D11", "D12"], "invoice & payment"),
    "P9": (["D13"], "grade boundary"),
}
ACTORS = [("Administrator", 90, 30), ("Teacher", 620, 30), ("Student", 1150, 30)]


STORE_NAMES = dict(
    [s for row in STORE_ROWS for s in row])
STORE_Y0, STORE_GAP, STORE_H = 330, 58, 44


def dfd_level1():
    c = Svg(1440, 620, "Data flow diagram, level 1")
    boxes = {}

    for i, (pid, title, roles) in enumerate(PROCESS_DEFS):
        x = PROCESS_COL(i)
        c.rect(x, PP_Y, PP_W, PP_H, fill=PROCESS_FILL, stroke=PROCESS_STROKE, rx=10, sw=1.8)
        c.text(x + PP_W / 2, PP_Y + 22, pid, size=13, anchor="middle",
               fill=PROCESS_STROKE, weight="bold")
        for j, ln in enumerate(title.split("\n")):
            c.text(x + PP_W / 2, PP_Y + 46 + j * 17, ln, size=12.5, anchor="middle", weight="bold")
        c.text(x + PP_W / 2, PP_Y + 82, roles, size=9.5, anchor="middle", fill="#64748b")
        boxes[pid] = (x, PP_Y, PP_W, PP_H)

    for name, ax, ay in ACTORS:
        c.rect(ax - 100, ay, 200, 46, fill="#e0f2fe", stroke="#0369a1", rx=4, sw=1.6)
        c.text(ax, ay + 29, name, size=13.5, anchor="middle", weight="bold")
        target = boxes["P1"][0] + 30
        c.path([(ax, ay + 46), (target, PP_Y)])
        c.label(ax + (target - ax) * 0.25, (ay + 46 + PP_Y) / 2, "login credentials", size=10)

    for i, (pid, title, _roles) in enumerate(PROCESS_DEFS):
        stores, label = STORE_FLOWS[pid]
        px = PROCESS_COL(i)
        for k, sid in enumerate(stores):
            y = STORE_Y0 + STORE_GAP * k
            c.rect(px, y, PP_W, STORE_H, fill=STORE_FILL, stroke="#475569", sw=1.4)
            c.line((px, y), (px + 14, y))
            c.text(px + 8, y + 18, sid, size=11, weight="bold")
            c.text(px + 8, y + 34, STORE_NAMES[sid], size=10)
        c.path([(px + PP_W / 2, PP_Y + PP_H), (px + PP_W / 2, STORE_Y0)])
        c.label(px + PP_W / 2, PP_Y + PP_H + 34, label, size=9.5)

    c.caption("P9 additionally reads D2, D9, D10 and D11/D12 to assemble report cards, class results and fee statements.")
    return c.save("diagrams/figure-dfd-1.svg")


# --------------------------------------------------------------------------
# Figure 4: use-case diagram
# --------------------------------------------------------------------------

UC_W, UC_H = 250, 52


def stick_figure(c, x, y, label):
    c.line((x, y), (x, y + 40), arrow=False)
    c.path([(x - 22, y + 14), (x + 22, y + 14)], arrow=False)
    c.line((x, y + 40), (x - 18, y + 66), arrow=False)
    c.line((x, y + 40), (x + 18, y + 66), arrow=False)
    c.rect(x - 11, y - 24, 22, 22, fill="#ffffff", stroke=ACTOR_STROKE, rx=11, sw=1.6)
    c.text(x, y + 88, label, size=13, anchor="middle", weight="bold",
           style="stroke='white' stroke-width='5' paint-order='stroke'")


def use_case():
    c = Svg(1240, 1060, "Use case diagram")
    c.rect(250, 30, 700, 990, fill="#fafafa", stroke="#94a3b8", rx=6, sw=1.4)
    c.text(600, 56, "School Management System", size=14.5, anchor="middle", weight="bold")

    left = [
        "Manage user accounts", "View audit trail", "Add student record",
        "Assign student to class", "Manage teacher records", "Manage classes",
        "Define subjects & curriculum", "Assign teacher to class-subject",
        "Create exam session", "Approve & publish results", "Record fee payment",
        "Generate class results",
    ]
    right = [
        "Take daily attendance", "Enter examination scores", "View subject results",
        "Print report card", "View my results", "View my attendance",
        "View my fee balance", "Change my password",
    ]

    oval = {}

    def put(name, cx, cy):
        c.rect(cx - UC_W / 2, cy - UC_H / 2, UC_W, UC_H, fill=USECASE_FILL,
               stroke=USECASE_STROKE, rx=UC_H / 2, sw=1.5)
        c.text(cx, cy + 4, name, size=12, anchor="middle")
        oval[name] = (cx, cy)

    put("Authenticate user", 600, 100)
    for i, name in enumerate(left):
        put(name, 400, 190 + i * 62)
    for i, name in enumerate(right):
        put(name, 800, 190 + i * 62)
    put("Export report as CSV", 400, 960)

    stick_figure(c, 130, 400, "Administrator")
    stick_figure(c, 1110, 300, "Teacher")
    stick_figure(c, 1110, 760, "Student")

    admin_uses = left + ["Export report as CSV"]
    teacher_uses = ["Take daily attendance", "Enter examination scores",
                    "View subject results", "Print report card"]
    student_uses = ["View my results", "View my attendance", "View my fee balance",
                    "Change my password"]

    for name, ax, ay, uses in (("Administrator", 130, 440, admin_uses),
                               ("Teacher", 1110, 340, teacher_uses),
                               ("Student", 1110, 800, student_uses)):
        for u in uses:
            cx, cy = oval[u]
            edge = (cx - UC_W / 2, cy) if ax < cx else (cx + UC_W / 2, cy)
            c.line((ax, ay), edge, color="#475569", arrow=False)

    for u in ("Take daily attendance", "Enter examination scores", "Manage user accounts"):
        cx, cy = oval[u]
        c.path([(cx, cy - UC_H / 2), (600 + (40 if cx > 600 else -40), 126)], dash="6 4")
    c.text(690, 150, "«include»", size=11, anchor="middle", fill="#475569")

    cx, cy = oval["Export report as CSV"]
    gx, gy = oval["Generate class results"]
    c.path([(cx, cy - UC_H / 2), (gx, gy + UC_H / 2)], dash="6 4")
    c.text((cx + gx) / 2 + 8, (cy + gy) / 2, "«extend»", size=11, anchor="middle", fill="#475569")

    c.caption("Solid lines are actor associations; dashed lines show «include» and «extend» relationships.")
    return c.save("diagrams/figure-use-case.svg")


def main():
    os.makedirs(os.path.join(OUT_DIR, "diagrams"), exist_ok=True)
    print(erd())
    print(dfd_level0())
    print(dfd_level1())
    print(use_case())


if __name__ == "__main__":
    main()
