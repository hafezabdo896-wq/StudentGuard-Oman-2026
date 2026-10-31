import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "studentguard.db"

st.set_page_config(page_title="StudentGuard", page_icon="🎓", layout="wide")

def db():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_no TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            grade TEXT NOT NULL,
            class_name TEXT NOT NULL,
            guardian_phone TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id),
            day TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT DEFAULT '',
            UNIQUE(student_id, day)
        );
        CREATE TABLE IF NOT EXISTS incidents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id),
            day TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            recommendation TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'مسجل',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS actions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER REFERENCES incidents(id),
            student_id INTEGER NOT NULL REFERENCES students(id),
            action_type TEXT NOT NULL,
            assigned_to TEXT DEFAULT '',
            assigned_day TEXT NOT NULL,
            approved_by TEXT DEFAULT '',
            due_day TEXT DEFAULT '',
            state TEXT NOT NULL DEFAULT 'مقترح',
            result_note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

def audit(event, details):
    with db() as con:
        con.execute("INSERT INTO audit(event,details,created_at) VALUES(?,?,?)",
                    (event, details, datetime.now().isoformat(timespec="seconds")))

def students_df():
    with db() as con:
        return pd.read_sql_query("SELECT * FROM students ORDER BY grade,class_name,full_name", con)

def student_options():
    df = students_df()
    return {f"{r.student_no} — {r.full_name} ({r.grade}/{r.class_name})": int(r.id)
            for r in df.itertuples()}

def metric_count(sql, params=()):
    with db() as con:
        return con.execute(sql, params).fetchone()[0]

init_db()

st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; text-align: right; }
[data-testid="stSidebar"] { direction: rtl; }
div[data-testid="stMetric"] { background:#f4f7fb; padding:12px; border-radius:12px; }
.stButton>button { border-radius:9px; }
</style>
""", unsafe_allow_html=True)

st.title("🎓 StudentGuard")
st.caption("نظام مدرسي تجريبي لمتابعة الحضور والسلوك والإجراءات التربوية")

with st.sidebar:
    st.header("القائمة الرئيسية")
    page = st.radio("انتقل إلى", [
        "لوحة التحكم", "إدارة الطلبة", "الحضور والغياب",
        "السلوك والمخالفات", "الإجراءات التربوية", "التقارير"
    ])
    st.divider()
    st.caption("نسخة تجريبية — القرار النهائي للمدرسة والجهة المختصة.")

if page == "لوحة التحكم":
    st.subheader("ملخص اليوم")
    today = date.today().isoformat()
    a,b,c,d = st.columns(4)
    a.metric("إجمالي الطلبة", metric_count("SELECT COUNT(*) FROM students"))
    b.metric("غياب اليوم", metric_count("SELECT COUNT(*) FROM attendance WHERE day=? AND status='غائب'", (today,)))
    c.metric("تأخر اليوم", metric_count("SELECT COUNT(*) FROM attendance WHERE day=? AND status='متأخر'", (today,)))
    d.metric("مخالفات مسجلة", metric_count("SELECT COUNT(*) FROM incidents"))
    st.info("ابدأ بإضافة الطلبة، ثم سجّل الحضور أو الواقعة السلوكية. يمكنك تجربة النظام ببيانات تجريبية من صفحة إدارة الطلبة.")
    with db() as con:
        recent = pd.read_sql_query("""
        SELECT i.day AS التاريخ,s.full_name AS الطالب,i.category AS التصنيف,
               i.description AS التفاصيل,i.recommendation AS التوصية,i.status AS الحالة
        FROM incidents i JOIN students s ON s.id=i.student_id
        ORDER BY i.id DESC LIMIT 8
        """, con)
    st.markdown("#### أحدث الوقائع")
    st.dataframe(recent, use_container_width=True, hide_index=True)

elif page == "إدارة الطلبة":
    st.subheader("إضافة طالب")
    with st.form("add_student", clear_on_submit=True):
        c1,c2 = st.columns(2)
        no = c1.text_input("الرقم المدرسي *")
        name = c2.text_input("اسم الطالب الكامل *")
        c3,c4,c5 = st.columns(3)
        grade = c3.text_input("الصف *", placeholder="مثال: العاشر")
        cls = c4.text_input("الشعبة *", placeholder="مثال: 1")
        phone = c5.text_input("هاتف ولي الأمر")
        submitted = st.form_submit_button("حفظ الطالب", type="primary")
        if submitted:
            if not all([no.strip(), name.strip(), grade.strip(), cls.strip()]):
                st.error("أكمل الحقول الإلزامية.")
            else:
                try:
                    with db() as con:
                        con.execute("""INSERT INTO students(student_no,full_name,grade,class_name,guardian_phone,created_at)
                        VALUES(?,?,?,?,?,?)""",
                        (no.strip(),name.strip(),grade.strip(),cls.strip(),phone.strip(),datetime.now().isoformat(timespec="seconds")))
                    audit("إضافة طالب", f"{no} - {name}")
                    st.success("تم حفظ الطالب.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("الرقم المدرسي مستخدم مسبقًا.")
    st.divider()
    st.markdown("#### قائمة الطلبة")
    df = students_df()
    st.dataframe(df[["student_no","full_name","grade","class_name","guardian_phone"]] if not df.empty else df,
                 use_container_width=True, hide_index=True)
    if not df.empty:
        st.download_button("تنزيل قائمة الطلبة CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           "students.csv", "text/csv")
    with st.expander("إضافة بيانات تجريبية للعرض (اختياري)"):
        st.warning("أضف هذه البيانات فقط إذا كانت القاعدة فارغة.")
        if st.button("إضافة 3 طلبة تجريبيين"):
            samples = [("1001","أحمد سالم","العاشر","1"),("1002","مريم خالد","العاشر","1"),("1003","سعيد علي","التاسع","2")]
            with db() as con:
                for row in samples:
                    try:
                        con.execute("INSERT INTO students(student_no,full_name,grade,class_name,created_at) VALUES(?,?,?,?,?)",
                                    (*row,datetime.now().isoformat(timespec="seconds")))
                    except sqlite3.IntegrityError:
                        pass
            audit("بيانات تجريبية", "إضافة عينة عرض")
            st.success("تمت إضافة البيانات التجريبية غير الحقيقية.")
            st.rerun()

elif page == "الحضور والغياب":
    st.subheader("تسجيل الحضور")
    opts = student_options()
    if not opts:
        st.warning("أضف طالبًا أولًا من صفحة إدارة الطلبة.")
    else:
        with st.form("attendance_form"):
            who = st.selectbox("الطالب", list(opts.keys()))
            day = st.date_input("التاريخ", value=date.today())
            status = st.selectbox("الحالة", ["حاضر","غائب","متأخر","بعذر"])
            note = st.text_input("ملاحظات")
            save = st.form_submit_button("حفظ سجل الحضور", type="primary")
            if save:
                try:
                    with db() as con:
                        con.execute("INSERT INTO attendance(student_id,day,status,note) VALUES(?,?,?,?)",
                                    (opts[who],day.isoformat(),status,note.strip()))
                    audit("تسجيل حضور", f"{who} - {day} - {status}")
                    st.success("تم تسجيل الحضور.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("يوجد سجل لهذا الطالب في هذا التاريخ. لا يمكن تكرار التسجيل.")
    st.divider()
    with db() as con:
        att = pd.read_sql_query("""SELECT a.day AS التاريخ,s.student_no AS الرقم المدرسي,
        s.full_name AS الطالب,s.grade AS الصف,s.class_name AS الشعبة,a.status AS الحالة,a.note AS ملاحظات
        FROM attendance a JOIN students s ON s.id=a.student_id ORDER BY a.day DESC,a.id DESC""", con)
    st.dataframe(att, use_container_width=True, hide_index=True)
    if not att.empty:
        st.download_button("تنزيل سجل الحضور CSV", att.to_csv(index=False).encode("utf-8-sig"),
                           "attendance.csv", "text/csv")

elif page == "السلوك والمخالفات":
    st.subheader("تسجيل واقعة سلوكية")
    opts = student_options()
    if not opts:
        st.warning("أضف طالبًا أولًا.")
    else:
        with st.form("incident_form"):
            who = st.selectbox("الطالب", list(opts.keys()))
            day = st.date_input("تاريخ الواقعة", value=date.today())
            category = st.selectbox("تصنيف الواقعة", [
                "سلوك يومي / مخالفة بسيطة", "مخالفة متوسطة", "مخالفة جسيمة",
                "واقعة تتطلب إحالة للإدارة"
            ])
            desc = st.text_area("وصف الواقعة بدقة وموضوعية *", placeholder="اكتب ما حدث دون أوصاف جارحة أو أحكام مسبقة.")
            rec = st.text_area("التوصية الأولية (اختياري)", placeholder="توصية للمراجعة وفق لائحة المدرسة والوزارة.")
            save = st.form_submit_button("تسجيل الواقعة", type="primary")
            if save:
                if not desc.strip():
                    st.error("اكتب وصف الواقعة.")
                else:
                    with db() as con:
                        con.execute("""INSERT INTO incidents(student_id,day,category,description,recommendation,status,created_at)
                        VALUES(?,?,?,?,?,?,?)""",
                        (opts[who],day.isoformat(),category,desc.strip(),rec.strip(),"مسجل",datetime.now().isoformat(timespec="seconds")))
                    audit("تسجيل واقعة", f"{who} - {category}")
                    st.success("سُجلت الواقعة. يجب مراجعة التوصية واعتماد أي إجراء من المسؤول المختص.")
                    st.rerun()
    st.divider()
    with db() as con:
        inc = pd.read_sql_query("""SELECT i.id AS رقم,s.full_name AS الطالب,i.day AS التاريخ,
        i.category AS التصنيف,i.description AS الواقعة,i.recommendation AS التوصية,i.status AS الحالة
        FROM incidents i JOIN students s ON s.id=i.student_id ORDER BY i.id DESC""", con)
    st.dataframe(inc, use_container_width=True, hide_index=True)
    if not inc.empty:
        st.download_button("تنزيل سجل الوقائع CSV", inc.to_csv(index=False).encode("utf-8-sig"),
                           "incidents.csv", "text/csv")

elif page == "الإجراءات التربوية":
    st.subheader("متابعة الإجراءات التربوية والإصلاحية")
    st.caption("هذه الصفحة لتنظيم إجراء تقترحه المدرسة وتعتمده إداريًا؛ لا تجعل النشاط عقوبة تلقائية ولا تستخدم إجراءً مهينًا أو خطرًا.")
    opts = student_options()
    with db() as con:
        incidents = pd.read_sql_query("""SELECT i.id,s.full_name,i.day,i.category,i.description
        FROM incidents i JOIN students s ON s.id=i.student_id ORDER BY i.id DESC""", con)
    if not opts:
        st.warning("أضف طلبة أولًا.")
    else:
        with st.form("action_form"):
            student_label = st.selectbox("الطالب", list(opts.keys()))
            incident_map = {"بدون ربط بواقعة": None}
            for r in incidents.itertuples():
                incident_map[f"واقعة #{r.id} — {r.full_name} — {r.day}"] = int(r.id)
            incident_label = st.selectbox("الواقعة المرتبطة", list(incident_map.keys()))
            action_type = st.selectbox("نوع الإجراء المقترح", [
                "جلسة إرشاد وتوعية", "اعتذار وإصلاح العلاقة", "ترتيب الفصل بإشراف",
                "مشاركة تطوعية في المحافظة على المرافق", "تنظيف مساحة محددة بإشراف وموافقة الإدارة",
                "متابعة سلوكية", "إجراء آخر معتمد من المدرسة"
            ])
            assigned = st.text_input("المسؤول عن المتابعة")
            assigned_day = st.date_input("تاريخ التكليف", value=date.today())
            due = st.date_input("موعد المتابعة / الإنجاز", value=date.today())
            approver = st.text_input("اعتماد المسؤول المختص (يُترك فارغًا حتى الاعتماد)")
            state = st.selectbox("الحالة", ["مقترح","معتمد","قيد التنفيذ","مكتمل","ملغى"])
            result = st.text_area("نتيجة التنفيذ / ملاحظات")
            save = st.form_submit_button("حفظ الإجراء")
            if save:
                with db() as con:
                    con.execute("""INSERT INTO actions(incident_id,student_id,action_type,assigned_to,assigned_day,
                    approved_by,due_day,state,result_note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (incident_map[incident_label],opts[student_label],action_type,assigned.strip(),
                     assigned_day.isoformat(),approver.strip(),due.isoformat(),state,result.strip(),
                     datetime.now().isoformat(timespec="seconds")))
                audit("إضافة إجراء", f"{student_label} - {action_type} - {state}")
                st.success("تم حفظ الإجراء.")
                st.rerun()
    st.divider()
    with db() as con:
        actions = pd.read_sql_query("""SELECT a.id AS رقم,s.full_name AS الطالب,a.action_type AS الإجراء,
        a.assigned_to AS المسؤول,a.assigned_day AS تاريخ_التكليف,a.approved_by AS المعتمد,
        a.due_day AS موعد_المتابعة,a.state AS الحالة,a.result_note AS النتيجة
        FROM actions a JOIN students s ON s.id=a.student_id ORDER BY a.id DESC""", con)
    st.dataframe(actions, use_container_width=True, hide_index=True)
    if not actions.empty:
        st.download_button("تنزيل الإجراءات CSV", actions.to_csv(index=False).encode("utf-8-sig"),
                           "actions.csv", "text/csv")

elif page == "التقارير":
    st.subheader("تقارير ومؤشرات")
    opts = student_options()
    if opts:
        selected = st.selectbox("اختر الطالب لعرض ملفه", list(opts.keys()))
        sid = opts[selected]
        with db() as con:
            st.markdown("#### الحضور")
            a = pd.read_sql_query("SELECT day AS التاريخ,status AS الحالة,note AS ملاحظات FROM attendance WHERE student_id=? ORDER BY day DESC", con, params=(sid,))
            st.dataframe(a, use_container_width=True, hide_index=True)
            st.markdown("#### الوقائع السلوكية")
            b = pd.read_sql_query("SELECT day AS التاريخ,category AS التصنيف,description AS الواقعة,recommendation AS التوصية FROM incidents WHERE student_id=? ORDER BY day DESC", con, params=(sid,))
            st.dataframe(b, use_container_width=True, hide_index=True)
            st.markdown("#### الإجراءات")
            c = pd.read_sql_query("SELECT action_type AS الإجراء,state AS الحالة,assigned_day AS تاريخ_التكليف,due_day AS موعد_المتابعة,result_note AS النتيجة FROM actions WHERE student_id=? ORDER BY id DESC", con, params=(sid,))
            st.dataframe(c, use_container_width=True, hide_index=True)
    else:
        st.info("أضف طلبة لعرض التقارير.")
    st.divider()
    with db() as con:
        audit_df = pd.read_sql_query("SELECT created_at AS الوقت,event AS العملية,details AS التفاصيل FROM audit ORDER BY id DESC LIMIT 100", con)
    with st.expander("سجل العمليات"):
        st.dataframe(audit_df, use_container_width=True, hide_index=True)

st.divider()
st.caption("StudentGuard | نموذج أولي للعرض والتجربة. لا يُعد بديلًا عن اللائحة الرسمية أو نظام الوزارة، ويجب مراجعة واعتماد الإجراءات من إدارة المدرسة.")
