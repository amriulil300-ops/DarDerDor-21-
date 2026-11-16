"""DarDerDor21+ : aplikasi koleksi video berbasis Streamlit.

Fitur: gerbang usia 21+, upload, putar, unduh, hapus, kategori, artis,
negara asal, durasi, resolusi (360p-2K), pencarian, filter, dan urutan.
Metadata disimpan di SQLite (koleksi.db), file video di folder videos/.
"""
import sqlite3
import uuid
from pathlib import Path

import streamlit as st

try:
    import cv2  # opsional: dipakai untuk membaca durasi & resolusi otomatis
except ImportError:
    cv2 = None

BASE = Path(__file__).parent
VID_DIR = BASE / "videos"
VID_DIR.mkdir(exist_ok=True)
DB_PATH = BASE / "koleksi.db"

CATS = ["Drama", "Komedi", "Dokumenter", "Musik", "Aksi", "Romansa"]
NEG = ["Indonesia", "Jepang", "Korea Selatan", "Amerika Serikat", "Brasil", "Prancis"]
RES = ["360p", "480p", "720p", "1080p", "2K"]
EXT = ["mp4", "webm", "mov", "mkv", "avi"]

st.set_page_config(page_title="DarDerDor21+", page_icon="🎬", layout="wide")


# ---------- database ----------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS videos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, category TEXT, artist TEXT, country TEXT,
            duration REAL, resolution TEXT, filename TEXT, orig_name TEXT,
            created TEXT DEFAULT CURRENT_TIMESTAMP)"""
    )
    conn.commit()
    conn.close()


def all_videos():
    conn = db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM videos")]
    conn.close()
    return rows


# ---------- util ----------
def fmt(sec):
    sec = int(round(sec or 0))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def res_label(side):
    if side <= 400:
        return "360p"
    if side <= 600:
        return "480p"
    if side <= 900:
        return "720p"
    if side <= 1260:
        return "1080p"
    return "2K"


def probe(path):
    """Kembalikan (durasi_detik, resolusi) atau (None, None) jika tidak terbaca."""
    if cv2 is None:
        return None, None
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0
    finally:
        cap.release()
    dur = frames / fps if fps and frames > 0 else None
    res = res_label(min(w, h)) if w and h else None
    return dur, res


def save_video(file, title, category, artist, country, res_choice, dur_manual):
    ext = file.name.rsplit(".", 1)[-1].lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    path = VID_DIR / fname
    with open(path, "wb") as out:
        out.write(file.getbuffer())
    dur, res = probe(path)
    if dur is None:
        dur = float(dur_manual)
    if res_choice != "Otomatis":
        res = res_choice
    if res is None:
        res = "720p"
    conn = db()
    conn.execute(
        "INSERT INTO videos(title,category,artist,country,duration,resolution,filename,orig_name)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (title, category, artist, country, dur, res, fname, file.name),
    )
    conn.commit()
    conn.close()


def delete_video(vid):
    conn = db()
    row = conn.execute("SELECT filename FROM videos WHERE id=?", (vid,)).fetchone()
    if row:
        (VID_DIR / row["filename"]).unlink(missing_ok=True)
        conn.execute("DELETE FROM videos WHERE id=?", (vid,))
        conn.commit()
    conn.close()


# ---------- gerbang usia ----------
init_db()
if "ok" not in st.session_state:
    st.session_state.ok = False
if "sel" not in st.session_state:
    st.session_state.sel = None

if not st.session_state.ok:
    st.title("DarDerDor21+")
    st.warning(
        "Situs ini hanya untuk pengguna berusia 21 tahun ke atas. Dengan masuk, "
        "Anda menyatakan sudah cukup umur dan mematuhi hukum yang berlaku."
    )
    if st.button("Saya 21+, masuk", type="primary"):
        st.session_state.ok = True
        st.rerun()
    st.stop()

videos = all_videos()

# ---------- sidebar: filter + upload ----------
with st.sidebar:
    st.header("🎬 DarDerDor21+")
    q = st.text_input("Cari judul atau artis")
    cats = sorted(set(CATS) | {v["category"] for v in videos})
    negs = sorted(set(NEG) | {v["country"] for v in videos})
    artists = sorted({v["artist"] for v in videos})
    f_cat = st.selectbox("Kategori", ["Semua"] + cats)
    f_neg = st.selectbox("Negara asal", ["Semua"] + negs)
    f_art = st.selectbox("Artis", ["Semua"] + artists)
    f_res = st.selectbox("Resolusi", ["Semua"] + RES)
    sort = st.selectbox("Urutkan", ["Terbaru", "Terpanjang", "Terpendek", "Judul A-Z"])

    st.divider()
    st.subheader("⬆ Upload video")
    with st.form("upload", clear_on_submit=True):
        file = st.file_uploader("File video", type=EXT)
        title = st.text_input("Judul")
        category = st.selectbox("Kategori video", cats)
        artist = st.text_input("Artis")
        country = st.selectbox("Negara asal video", negs)
        country_other = st.text_input("Negara lain (opsional, menimpa pilihan di atas)")
        res_choice = st.selectbox("Resolusi", ["Otomatis"] + RES)
        dur_manual = st.number_input(
            "Durasi (detik), dipakai jika tidak terbaca otomatis", min_value=0, value=0
        )
        go = st.form_submit_button("Simpan", type="primary")
    if go:
        if not file or not title.strip() or not artist.strip():
            st.error("File, judul, dan artis wajib diisi.")
        else:
            save_video(
                file, title.strip(), category, artist.strip(),
                country_other.strip() or country, res_choice, dur_manual,
            )
            st.success("Video tersimpan.")
            st.rerun()

# ---------- filter + urut ----------
ql = q.lower().strip()
shown = [
    v for v in videos
    if (f_cat == "Semua" or v["category"] == f_cat)
    and (f_neg == "Semua" or v["country"] == f_neg)
    and (f_art == "Semua" or v["artist"] == f_art)
    and (f_res == "Semua" or v["resolution"] == f_res)
    and (not ql or ql in f'{v["title"]} {v["artist"]}'.lower())
]
if sort == "Terbaru":
    shown.sort(key=lambda v: v["id"], reverse=True)
elif sort == "Terpanjang":
    shown.sort(key=lambda v: v["duration"] or 0, reverse=True)
elif sort == "Terpendek":
    shown.sort(key=lambda v: v["duration"] or 0)
else:
    shown.sort(key=lambda v: v["title"].lower())

st.title("DarDerDor21+")
st.caption(f"{len(shown)} dari {len(videos)} video")

# ---------- panel putar & unduh ----------
sel = next((v for v in videos if v["id"] == st.session_state.sel), None)
if sel:
    path = VID_DIR / sel["filename"]
    with st.container(border=True):
        st.subheader(sel["title"])
        st.caption(
            f'{sel["category"]} · {sel["artist"]} · {sel["country"]} · '
            f'{sel["resolution"]} · {fmt(sel["duration"])}'
        )
        if path.exists():
            st.video(str(path))
            c1, c2, c3 = st.columns(3)
            ext = sel["orig_name"].rsplit(".", 1)[-1]
            with open(path, "rb") as fh:
                c1.download_button(
                    "⬇ Unduh", fh, file_name=f'{sel["title"]}.{ext}',
                    key=f'dl{sel["id"]}',
                )
            if c2.button("🗑 Hapus", key=f'del{sel["id"]}'):
                delete_video(sel["id"])
                st.session_state.sel = None
                st.rerun()
            if c3.button("Tutup", key="close"):
                st.session_state.sel = None
                st.rerun()
        else:
            st.error("File video tidak ditemukan di server.")

# ---------- grid ----------
if not shown:
    st.info("Belum ada video. Upload video lewat panel di sebelah kiri.")
else:
    cols = st.columns(3)
    for i, v in enumerate(shown):
        with cols[i % 3].container(border=True):
            st.markdown(f"**{v['title']}**")
            st.caption(f"{v['artist']} · {v['country']}")
            st.write(f"`{v['category']}`  `{v['resolution']}`  `{fmt(v['duration'])}`")
            if st.button("▶ Putar / Unduh", key=f"open{v['id']}"):
                st.session_state.sel = v["id"]
                st.rerun()
