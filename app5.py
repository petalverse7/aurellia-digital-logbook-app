import streamlit as st
import sqlite3
import pandas as pd
import json
import base64
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
from PyPDF2 import PdfMerger

# ==========================================
# 1. KONFIGURASI TAMPILAN & WARNA PASTEL
# ==========================================
st.set_page_config(page_title="Digital Clinical Logbook", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #e8f5e9; }
    .css-1d391kg { background-color: #e3f2fd; }
    h1, h2, h3, h4, p, label { color: #212529 !important; }
    .stButton>button { background-color: #81c784; color: white !important; border: none; border-radius: 8px; font-weight: bold; }
    .stButton>button:hover { background-color: #66bb6a; }
    div[data-testid="stForm"] { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .readonly-text { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border: 1px solid #dee2e6; color: #495057; }
    .header-col { font-weight: bold; padding-bottom: 10px; border-bottom: 2px solid #dee2e6; margin-bottom: 10px; font-size: 14px; text-align: center;}
    
    .badge { padding: 5px 10px; border-radius: 15px; font-size: 11px; font-weight: bold; color: #fff; text-align: center; display: inline-block; width: 100%;}
    .bg-draft { background-color: #9e9e9e; }
    .bg-ci { background-color: #ff9800; }
    .bg-dsn { background-color: #03a9f4; }
    .bg-selesai { background-color: #4caf50; }
    
    /* Style custom Kotak Catatan Reviewers di Menu Tervalidasi */
    .table-komen {
        width: 100%;
        background-color: #ffffff;
        border-collapse: collapse;
        margin-top: 8px;
        margin-bottom: 15px;
        border: 1px solid #dee2e6;
    }
    .table-komen td {
        padding: 10px 15px;
        border: 1px solid #dee2e6;
        color: #212529 !important;
        font-size: 14px;
        vertical-align: top;
    }
    .role-label {
        font-weight: bold;
        background-color: #f8f9fa;
        width: 200px;
    }
    </style>
""", unsafe_allow_html=True)

hari_dict = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}

# ==========================================
# 2. SETUP DATABASE (SQLITE)
# ==========================================
conn = sqlite3.connect('logbook_digital.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, password TEXT, role TEXT, nama TEXT, nim_nip TEXT, daftar_ci TEXT, daftar_dosen TEXT, ttd_image TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logbooks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tanggal TEXT, matkul TEXT, ruangan TEXT, 
                 hari_ke INTEGER, kegiatan_json TEXT, kasus TEXT, status TEXT, nama_ci_terpilih TEXT, nama_dosen_terpilih TEXT, created_at TEXT,
                 komen_ci TEXT, komen_dosen TEXT)''')
    conn.commit()

create_tables()

# ==========================================
# 3. FUNGSI GENERATOR PDF
# ==========================================
def generate_pdf(nama, nim, tanggal_str, matkul, ruangan, hari_ke, kegiatan_df, kasus, nama_ci="", nip_ci="", ttd_ci=None, nama_dosen="", nip_dosen="", ttd_dosen=None, komen_ci="", komen_dosen=""):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='TitleStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, alignment=TA_CENTER, spaceAfter=20)
    
    elements.append(Paragraph("<u>LOGBOOK PRAKTIK KLINIK</u>", title_style))
    elements.append(Spacer(1, 10))
    
    data_diri = [
        ["Nama Mahasiswa", ":", nama], ["NIM", ":", nim],
        ["Hari, Tanggal", ":", tanggal_str], ["Mata Kuliah", ":", matkul],
        ["Ruangan", ":", ruangan], ["Hari Ke -", ":", str(hari_ke)]
    ]
    t_diri = Table(data_diri, colWidths=[100, 20, 350], hAlign='LEFT')
    t_diri.setStyle(TableStyle([('FONT', (0,0), (-1,-1), 'Helvetica', 10), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    elements.append(t_diri)
    elements.append(Spacer(1, 15))
    
    kegiatan_data = [["Jam (WIB)", "Kegiatan", "Keterangan"]]
    cell_style = ParagraphStyle(name='CellStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=12)
    
    for index, row in kegiatan_df.iterrows():
        if pd.isna(row['Jam']) and pd.isna(row['Kegiatan']) and pd.isna(row['Keterangan']): continue
        jam_str = str(row['Jam'])[:5] if not pd.isna(row['Jam']) and str(row['Jam']).strip() not in ["", "None", "NaT"] else ""
        
        keg_val = str(row['Kegiatan']).replace('\n', '<br/>') if not pd.isna(row['Kegiatan']) else ""
        ket_val = str(row['Keterangan']).replace('\n', '<br/>') if not pd.isna(row['Keterangan']) else ""
        
        keg_para = Paragraph(keg_val, cell_style) if keg_val else ""
        ket_para = Paragraph(ket_val, cell_style) if ket_val else ""
        
        kegiatan_data.append([jam_str, keg_para, ket_para])
        
    t_kegiatan = Table(kegiatan_data, colWidths=[80, 220, 200])
    t_kegiatan.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(t_kegiatan)
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("<b>Kasus yang dikelola:</b>", styles['Normal']))
    elements.append(Spacer(1, 5))
    kasus_lines = kasus.split('\n') if kasus else []
    for i, line in enumerate(kasus_lines): elements.append(Paragraph(f"{i+1}. {line}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Tabel komentar selalu tercetak di bawah kasus (bila kosong berisi "-")
    elements.append(Paragraph("<b>Komentar</b>", styles['Normal']))
    elements.append(Spacer(1, 5))
    
    pdf_komen_ci = str(komen_ci).strip() if (komen_ci and str(komen_ci).strip() != "") else "-"
    pdf_komen_dosen = str(komen_dosen).strip() if (komen_dosen and str(komen_dosen).strip() != "") else "-"
    
    para_komen_ci = Paragraph(pdf_komen_ci.replace('\n', '<br/>'), cell_style)
    para_komen_dsn = Paragraph(pdf_komen_dosen.replace('\n', '<br/>'), cell_style)
    
    label_ci_para = Paragraph("<b>Pembimbing Klinik (CI)</b>", cell_style)
    label_dsn_para = Paragraph("<b>Dosen Akademik</b>", cell_style)
    
    pdf_komen_data = [
        [label_ci_para, para_komen_ci],
        [label_dsn_para, para_komen_dsn]
    ]
    
    t_pdf_komen = Table(pdf_komen_data, colWidths=[150, 350], hAlign='LEFT')
    t_pdf_komen.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(t_pdf_komen)
    elements.append(Spacer(1, 25))
    
    # Bagian penempelan gambar tanda tangan digital
    img_ci = Spacer(1, 40)
    if ttd_ci:
        try: img_ci = Image(BytesIO(base64.b64decode(ttd_ci)), width=1.5*72, height=0.8*72)
        except: pass
        
    img_dosen = Spacer(1, 40)
    if ttd_dosen:
        try: img_dosen = Image(BytesIO(base64.b64decode(ttd_dosen)), width=1.5*72, height=0.8*72)
        except: pass

    teks_nama_ci = f"<u>{nama_ci}</u>" if nama_ci else "________________________"
    teks_nip_ci = f"NIP/NIK: {nip_ci}" if nip_ci else "NIP/NIK: ...................."
    
    teks_nama_dsn = f"<u>{nama_dosen}</u>" if nama_dosen else "________________________"
    teks_nip_dsn = f"NIP/NIK: {nip_dosen}" if nip_dosen else "NIP/NIK: ...................."

    ttd_data = [
        [Paragraph("Mengetahui,", ParagraphStyle(name='c_top', alignment=TA_CENTER)), ""], 
        [Paragraph("Pembimbing Klinik", ParagraphStyle(name='c_mid', alignment=TA_CENTER)), Paragraph("Pembimbing Akademik", ParagraphStyle(name='c_mid', alignment=TA_CENTER))], 
        [img_ci, img_dosen], 
        [Paragraph(teks_nama_ci, ParagraphStyle(name='c_bot1', alignment=TA_CENTER)), Paragraph(teks_nama_dsn, ParagraphStyle(name='c_bot1', alignment=TA_CENTER))],
        [Paragraph(teks_nip_ci, ParagraphStyle(name='c_bot2', alignment=TA_CENTER)), Paragraph(teks_nip_dsn, ParagraphStyle(name='c_bot2', alignment=TA_CENTER))]
    ]
    
    t_ttd = Table(ttd_data, colWidths=[250, 250])
    t_ttd.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)), 
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), 
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5)
    ]))
    elements.append(t_ttd)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==========================================
# 4. MANAJEMEN SESI & HELPER
# ==========================================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'menu_aktif' not in st.session_state: st.session_state['menu_aktif'] = None
if 'edit_id' not in st.session_state: st.session_state['edit_id'] = None
if 'preview_pdf' not in st.session_state: st.session_state['preview_pdf'] = None
if 'preview_filename' not in st.session_state: st.session_state['preview_filename'] = ""

def get_user_data(nama, role):
    c.execute("SELECT nim_nip, ttd_image FROM users WHERE nama=? AND role=?", (nama, role))
    return c.fetchone()

# ==========================================
# 5. ANTARMUKA UTAMA
# ==========================================
if not st.session_state['logged_in']:
    st.title("🏥 Digital Clinical Logbook")
    menu = st.sidebar.selectbox("Menu Autentikasi", ["Masuk (Login)", "Daftar (Register)"])

    if menu == "Daftar (Register)":
        with st.form("register_form"):
            st.subheader("Buat Akun Baru")
            email = st.text_input("Email Aktif")
            password = st.text_input("Kata Sandi (Maks 8 Karakter)", type="password", max_chars=8)
            role = st.selectbox("Peran", ["Mahasiswa", "Dosen", "Pembimbing Klinik (CI)"])
            nama = st.text_input("Nama Lengkap")
            nim_nip = st.text_input("NIM (Mahasiswa) / NIP/NIK (Dosen/CI)")
            
            daftar_ci_input, daftar_dosen_input = "", ""
            
            if role == "Mahasiswa":
                st.markdown("---")
                st.markdown("**Pengaturan Data Pembimbing & Dosen (Khusus Mahasiswa)**")
                st.caption("Silakan kosongkan saja jika Anda mendaftar sebagai Pembimbing Klinik (CI) atau Dosen.")
                col1, col2 = st.columns(2)
                with col1: daftar_ci_input = st.text_area("Daftar Nama CI (Pisahkan dengan Enter):", placeholder="Budi Santoso\nSiti Aminah")
                with col2: daftar_dosen_input = st.text_area("Daftar Nama Dosen (Pisahkan dengan Enter):", placeholder="Dr. Andi Rahman\nNs. Sari Indah")

            if st.form_submit_button("Daftar"):
                c.execute('SELECT id FROM users WHERE email=?', (email,))
                existing_email = c.fetchone()
                
                c.execute('SELECT id FROM users WHERE nama=?', (nama,))
                existing_nama = c.fetchone()
                
                if existing_email:
                    st.error("❌ Gagal: Email tersebut sudah digunakan oleh pengguna lain! Silakan gunakan email lain.")
                elif existing_nama:
                    st.error("❌ Gagal: Nama Lengkap tersebut sudah terdaftar di sistem! Mohon gunakan nama lengkap unik / tambahkan gelar.")
                elif not email or not password or not nama:
                    st.warning("⚠️ Mohon lengkapi kolom Email, Kata Sandi, dan Nama Lengkap.")
                else:
                    c.execute('INSERT INTO users (email, password, role, nama, nim_nip, daftar_ci, daftar_dosen, ttd_image) VALUES (?,?,?,?,?,?,?,?)', 
                              (email, password, role, nama, nim_nip, daftar_ci_input, daftar_dosen_input, ""))
                    conn.commit()
                    st.success("🎉 Berhasil mendaftar! Silakan beralih ke menu Masuk (Login).")

    elif menu == "Masuk (Login)":
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Kata Sandi", type="password")
            if st.form_submit_button("Masuk"):
                c.execute('SELECT id, role, nama, nim_nip FROM users WHERE email=? AND password=?', (email, password))
                user = c.fetchone()
                if user:
                    st.session_state.update({'logged_in': True, 'user_id': user[0], 'role': user[1], 'nama': user[2], 'nim_nip': user[3]})
                    if user[1] == "Mahasiswa": st.session_state['menu_aktif'] = "👤 Profil Data Mahasiswa"
                    elif user[1] == "Pembimbing Klinik (CI)": st.session_state['menu_aktif'] = "👤 Profil Data Pembimbing Klinik (CI)"
                    elif user[1] == "Dosen": st.session_state['menu_aktif'] = "👤 Profil Data Dosen"
                    st.rerun()
                else: st.error("Email atau Kata Sandi salah!")

else:
    st.sidebar.title(f"Halo, {st.session_state['nama']}")
    st.sidebar.write(f"Peran: {st.session_state['role']}")
    st.sidebar.markdown("---")

    # ==========================================
    # DASHBOARD MAHASISWA
    # ==========================================
    if st.session_state['role'] == "Mahasiswa":
        menu_options = ["👤 Profil Data Mahasiswa", "📝 Pengisian Logbook", "📂 Riwayat (Tersimpan)", "✅ Logbook Tervalidasi", "🗂️ Ekspor Dokumen"]
        try: default_index = menu_options.index(st.session_state['menu_aktif'])
        except: default_index = 0
            
        pilihan_menu = st.sidebar.radio("Navigasi Dashboard", menu_options, index=default_index)
        st.session_state['menu_aktif'] = pilihan_menu 
        if st.sidebar.button("Keluar (Logout)"): st.session_state.clear(); st.rerun()

        if pilihan_menu == "👤 Profil Data Mahasiswa":
            st.title("👤 Profil Data Mahasiswa")
            c.execute("SELECT daftar_ci, daftar_dosen FROM users WHERE id=?", (st.session_state['user_id'],))
            current_data = c.fetchone()
            df_ci = pd.DataFrame([n.strip() for n in (current_data[0] or "").split('\n') if n.strip()], columns=["Nama CI"])
            df_dosen = pd.DataFrame([n.strip() for n in (current_data[1] or "").split('\n') if n.strip()], columns=["Nama Dosen"])
            
            with st.form("profil_form"):
                nama_baru = st.text_input("Nama Lengkap", value=st.session_state['nama'])
                nim_baru = st.text_input("NIM", value=st.session_state['nim_nip'])
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Daftar CI Anda**"); edited_ci = st.data_editor(df_ci, num_rows="dynamic", use_container_width=True)
                with col2:
                    st.markdown("**Daftar Dosen Anda**"); edited_dosen = st.data_editor(df_dosen, num_rows="dynamic", use_container_width=True)
                
                if st.form_submit_button("Simpan Data Profil"):
                    new_ci_str = "\n".join([str(n).strip() for n in edited_ci["Nama CI"].dropna().tolist() if str(n).strip()])
                    new_dosen_str = "\n".join([str(n).strip() for n in edited_dosen["Nama Dosen"].dropna().tolist() if str(n).strip()])
                    
                    c.execute('SELECT id FROM users WHERE nama=? AND id!=?', (nama_baru, st.session_state['user_id']))
                    nama_terpakai = c.fetchone()
                    
                    if nama_terpakai:
                        st.error("❌ Gagal update: Nama Lengkap tersebut sudah terdaftar pada pengguna lain!")
                    else:
                        c.execute("UPDATE users SET nama=?, nim_nip=?, daftar_ci=?, daftar_dosen=? WHERE id=?", (nama_baru, nim_baru, new_ci_str, new_dosen_str, st.session_state['user_id']))
                        conn.commit()
                        st.session_state['nama'], st.session_state['nim_nip'] = nama_baru, nim_baru
                        st.success("Profil berhasil diperbarui!")

        elif pilihan_menu == "📝 Pengisian Logbook":
            st.title("📚 Pengisian Logbook Praktik")
            def_tanggal = datetime.today().date()
            def_matkul, def_ruangan, def_harike, def_kasus = "", "", 1, ""
            def_kegiatan = pd.DataFrame([{"Jam": None, "Kegiatan": "", "Keterangan": ""} for _ in range(5)]) 
            
            if st.session_state['edit_id'] is not None:
                st.info(f"✏️ Anda sedang mengedit Logbook ID: {st.session_state['edit_id']}")
                c.execute("SELECT tanggal, matkul, ruangan, hari_ke, kegiatan_json, kasus FROM logbooks WHERE id=?", (st.session_state['edit_id'],))
                data_edit = c.fetchone()
                if data_edit:
                    try: 
                        str_tgl = data_edit[0].split(", ")[1]
                        def_tanggal = datetime.strptime(str_tgl, "%d/%m/%Y").date()
                    except: def_tanggal = datetime.today().date()
                    def_matkul, def_ruangan, def_harike = data_edit[1], data_edit[2], data_edit[3]
                    def_kegiatan = pd.DataFrame(json.loads(data_edit[4]))
                    if 'Jam' in def_kegiatan.columns:
                        def parse_jam(x):
                            try: return None if pd.isna(x) or str(x).strip() in ["", "None", "NaT"] else datetime.strptime(str(x)[:5], "%H:%M").time()
                            except: return None
                        def_kegiatan['Jam'] = def_kegiatan['Jam'].apply(parse_jam)
                    def_kasus = data_edit[5]
                if st.button("Batal Edit / Buat Baru"): 
                    st.session_state['edit_id'] = None
                    st.rerun()

            with st.form("logbook_form"):
                col1, col2 = st.columns(2)
                with col1:
                    tanggal = st.date_input("Hari, Tanggal", value=def_tanggal, format="DD/MM/YYYY")
                    if tanggal:
                        nama_hari = hari_dict[tanggal.weekday()]
                        st.markdown(f"<div style='margin-top:-15px; margin-bottom:15px; color:#4caf50; font-weight:bold; font-size:14px;'>✓ Terbaca: {nama_hari}, {tanggal.strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)
                    matkul = st.text_input("Mata Kuliah", value=def_matkul)
                with col2:
                    ruangan = st.text_input("Ruangan", value=def_ruangan)
                    hari_ke = st.number_input("Hari Ke-", min_value=1, value=def_harike)
                
                st.markdown("#### Tabel Kegiatan")
                edited_df = st.data_editor(def_kegiatan, num_rows="dynamic", use_container_width=True, column_config={"Jam": st.column_config.TimeColumn("Jam (24 Jam)", format="HH:mm", step=60)})
                st.markdown("#### Kasus")
                kasus = st.text_area("Kasus yang dikelola", value=def_kasus, height=100)
                
                if st.form_submit_button("Simpan Perubahan" if st.session_state['edit_id'] else "Simpan Draft"):
                    if tanggal:
                        format_tgl_lengkap = f"{nama_hari}, {tanggal.strftime('%d/%m/%Y')}"
                        edited_df['Jam'] = edited_df['Jam'].astype(str).replace(['NaT', 'None'], '')
                        keg_json = edited_df.to_json(orient="records")
                        timestamp_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        if st.session_state['edit_id']:
                            c.execute('''UPDATE logbooks SET tanggal=?, matkul=?, ruangan=?, hari_ke=?, kegiatan_json=?, kasus=?, created_at=? WHERE id=?''',
                                      (format_tgl_lengkap, matkul, ruangan, hari_ke, keg_json, kasus, timestamp_now, st.session_state['edit_id']))
                            conn.commit()
                            st.session_state['edit_id'] = None
                            st.toast("✅ Perubahan logbook berhasil disimpan!")
                        else:
                            c.execute('''INSERT INTO logbooks (user_id, tanggal, matkul, ruangan, hari_ke, kegiatan_json, kasus, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)''',
                                      (st.session_state['user_id'], format_tgl_lengkap, matkul, ruangan, hari_ke, keg_json, kasus, 'Draft', timestamp_now))
                            conn.commit()
                            st.toast("📋 Logbook baru berhasil disimpan!")
                        
                        st.session_state['menu_aktif'] = "📂 Riwayat (Tersimpan)"
                        st.rerun()

        elif pilihan_menu == "📂 Riwayat (Tersimpan)":
            st.title("📂 Riwayat Logbook (Tersimpan)")
            st.info("Seluruh dokumen Anda yang telah dibuat akan terekam di sini.")
            
            c.execute("SELECT id, tanggal, matkul, ruangan, status, nama_ci_terpilih, nama_dosen_terpilih, hari_ke, kegiatan_json, kasus, komen_ci, komen_dosen FROM logbooks WHERE user_id=? ORDER BY id DESC", (st.session_state['user_id'],))
            drafts = c.fetchall()
            
            c.execute("SELECT daftar_ci, daftar_dosen FROM users WHERE id=?", (st.session_state['user_id'],))
            d_lists = c.fetchone()
            ci_names = ["-- Pilih CI --"] + [n.strip() for n in (d_lists[0] or "").split('\n') if n.strip()]
            ds_names = ["-- Pilih Dosen --"] + [n.strip() for n in (d_lists[1] or "").split('\n') if n.strip()]

            if len(drafts) > 0:
                h_cols = st.columns([0.5, 1.8, 1.5, 1.2, 1, 1.5, 1.5, 1.5, 1.5])
                headers = ["No", "Hari, Tgl", "Matkul", "Ruangan", "Preview", "Pilih CI", "Pilih Dosen", "Status", "Aksi"]
                for i, col in enumerate(h_cols): col.markdown(f"<div class='header-col'>{headers[i]}</div>", unsafe_allow_html=True)

                for i, row in enumerate(drafts):
                    l_id, tgl, mk, rg, stat, saved_ci, saved_dosen, hk, k_json, kas, km_ci, km_ds = row
                    r_cols = st.columns([0.5, 1.8, 1.5, 1.2, 1, 1.5, 1.5, 1.5, 1.5])
                    
                    r_cols[0].write(str(i+1)); r_cols[1].write(tgl); r_cols[2].write(mk); r_cols[3].write(rg)
                    
                    if r_cols[4].button("👁️ Cek", key=f"prev_mhs_{l_id}"):
                        # FIX LOGIKA TTD: Validasi data penempelan gambar tanda tangan digital berdasarkan status verifikasi
                        ci_data = None
                        if saved_ci and saved_ci != "-- Pilih CI --":
                            ci_data = get_user_data(saved_ci, "Pembimbing Klinik (CI)")
                            
                        dsn_data = None
                        if saved_dosen and saved_dosen != "-- Pilih Dosen --":
                            dsn_data = get_user_data(saved_dosen, "Dosen")
                        
                        pdf_buf = generate_pdf(
                            st.session_state['nama'], st.session_state['nim_nip'], tgl, mk, rg, hk, 
                            pd.DataFrame(json.loads(k_json)), kasus=kas, 
                            nama_ci=saved_ci if saved_ci != "-- Pilih CI --" else "", 
                            nip_ci=ci_data[0] if ci_data else "", 
                            ttd_ci=ci_data[1] if (ci_data and stat in ['Menunggu Dosen', 'Selesai']) else None,
                            nama_dosen=saved_dosen if saved_dosen != "-- Pilih Dosen --" else "", 
                            nip_dosen=dsn_data[0] if dsn_data else "", 
                            ttd_dosen=dsn_data[1] if (dsn_data and stat == 'Selesai') else None,
                            komen_ci=km_ci, komen_dosen=km_ds
                        )
                        st.session_state['preview_pdf'] = pdf_buf
                        st.session_state['preview_filename'] = f"Logbook_{mk}.pdf"
                        st.rerun()
                    
                    is_sent = (stat != 'Draft')
                    idx_ci = ci_names.index(saved_ci) if saved_ci in ci_names else 0
                    idx_ds = ds_names.index(saved_dosen) if saved_dosen in ds_names else 0
                    terpilih_ci = r_cols[5].selectbox("CI", ci_names, index=idx_ci, key=f"ci_{l_id}", label_visibility="collapsed", disabled=is_sent)
                    terpilih_ds = r_cols[6].selectbox("Dosen", ds_names, index=idx_ds, key=f"ds_{l_id}", label_visibility="collapsed", disabled=is_sent)
                    
                    if stat == 'Draft': badge = "<span class='badge bg-draft'>Draft</span>"
                    elif stat == 'Menunggu CI': badge = "<span class='badge bg-ci'>Menunggu CI</span>"
                    elif stat == 'Menunggu Dosen': badge = "<span class='badge bg-dsn'>Menunggu Dosen</span>"
                    elif stat == 'Selesai': badge = "<span class='badge bg-selesai'>Tervalidasi</span>"
                    r_cols[7].markdown(badge, unsafe_allow_html=True)
                    
                    with r_cols[8]:
                        if stat == 'Draft':
                            if st.button("📝 Edit", key=f"ed_{l_id}"):
                                st.session_state['edit_id'] = l_id
                                st.session_state['menu_aktif'] = "📝 Pengisian Logbook"
                                st.rerun()
                            if st.button("Kirim ➔", type="primary", key=f"krm_{l_id}"):
                                if terpilih_ci == "-- Pilih CI --" or terpilih_ds == "-- Pilih Dosen --": st.error("Pilih CI & Dosen!")
                                else:
                                    c.execute("UPDATE logbooks SET status='Menunggu CI', nama_ci_terpilih=?, nama_dosen_terpilih=?, created_at=? WHERE id=?", (terpilih_ci, terpilih_ds, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), l_id))
                                    conn.commit(); st.rerun()
                        elif stat == 'Menunggu CI':
                            if st.button("Batal Kirim ✖", key=f"btl_{l_id}"):
                                c.execute("UPDATE logbooks SET status='Draft' WHERE id=?", (l_id,)); conn.commit(); st.rerun()
                        else:
                            st.markdown("<span style='color:grey; font-size:12px;'>Sesi Terkunci</span>", unsafe_allow_html=True)
            else: st.info("Tidak ada logbook tersimpan.")

        elif pilihan_menu == "✅ Logbook Tervalidasi":
            st.title("✅ Logbook Tervalidasi")
            c.execute("SELECT id, tanggal, matkul, ruangan, hari_ke, kegiatan_json, kasus, nama_ci_terpilih, nama_dosen_terpilih, komen_ci, komen_dosen FROM logbooks WHERE user_id=? AND status='Selesai'", (st.session_state['user_id'],))
            selesai_data = c.fetchall()
            if len(selesai_data) > 0:
                for i, row in enumerate(selesai_data):
                    l_id, tgl, mk, rg, hk, keg_json, kas, n_ci, n_ds, km_ci, km_ds = row
                    st.write(f"**{i+1}. {tgl} - {mk}**")
                    
                    html_box_final = f"""
                    <table class="table-komen">
                        <tr>
                            <td class="role-label">Pembimbing Klinik (CI)</td>
                            <td>{km_ci if km_ci else '-'}</td>
                        </tr>
                        <tr>
                            <td class="role-label">Dosen Academic</td>
                            <td>{km_ds if km_ds else '-'}</td>
                        </tr>
                    </table>
                    """
                    st.markdown(html_box_final, unsafe_allow_html=True)
                    
                    if st.button(f"👁️ Preview Logbook {i+1}", key=f"prev_selesai_{l_id}"):
                        ci_data = get_user_data(n_ci, "Pembimbing Klinik (CI)")
                        dsn_data = get_user_data(n_ds, "Dosen")
                        
                        pdf_buf = generate_pdf(st.session_state['nama'], st.session_state['nim_nip'], tgl, mk, rg, hk, pd.DataFrame(json.loads(keg_json)), kasus=kas, 
                                           nama_ci=n_ci, nip_ci=ci_data[0] if ci_data else "", ttd_ci=ci_data[1] if ci_data else None,
                                           nama_dosen=n_ds, nip_dosen=dsn_data[0] if dsn_data else "", ttd_dosen=dsn_data[1] if dsn_data else None,
                                           komen_ci=km_ci, komen_dosen=km_ds)
                        st.session_state['preview_pdf'] = pdf_buf
                        st.session_state['preview_filename'] = f"Final_{tgl}.pdf"
                        st.rerun()
                    st.markdown("---")
            else: st.info("Belum ada.")
        
        elif pilihan_menu == "🗂️ Ekspor Dokumen":
            st.title("🗂️ Ekspor & Rekap Dokumen")
            c.execute("SELECT id, tanggal, matkul, ruangan, hari_ke FROM logbooks WHERE user_id=? AND status='Selesai'", (st.session_state['user_id'],))
            hasil = c.fetchall()
            if len(hasil) > 0:
                df_eksport = pd.DataFrame(hasil, columns=['id', 'Hari, Tanggal', 'Mata Kuliah', 'Ruangan', 'Hari ke-'])
                df_eksport.insert(0, 'Ekspor', False); df_eksport.insert(1, 'No', range(1, len(df_eksport) + 1))
                edited_eksport = st.data_editor(df_eksport, hide_index=True, use_container_width=True, column_config={"Ekspor": st.column_config.CheckboxColumn("Ekspor (Ceklis)", default=False), "id": None}, disabled=["No", "Hari, Tanggal", "Mata Kuliah", "Ruangan", "Hari ke-"])
                
                if st.button("👁️ Proses Gabungan PDF", type="primary"):
                    selected_ids = edited_eksport[edited_eksport['Ekspor'] == True]['id'].tolist()
                    if not selected_ids: st.warning("Ceklis minimal 1 baris.")
                    else:
                        merger = PdfMerger()
                        placeholders = ','.join('?' for _ in selected_ids)
                        c.execute(f"SELECT l.tanggal, l.matkul, l.ruangan, l.hari_ke, l.kegiatan_json, l.kasus, l.nama_ci_terpilih, l.nama_dosen_terpilih, l.komen_ci, l.komen_dosen FROM logbooks l WHERE l.id IN ({placeholders})", selected_ids)
                        files_to_merge = c.fetchall()
                        for f in files_to_merge:
                            tgl, mk, rg, hk, keg_json, kas, n_ci, n_ds, km_ci, km_ds = f
                            ci_data = get_user_data(n_ci, "Pembimbing Klinik (CI)")
                            dsn_data = get_user_data(n_ds, "Dosen")
                            
                            pdf_buf = generate_pdf(st.session_state['nama'], st.session_state['nim_nip'], tgl, mk, rg, hk, pd.DataFrame(json.loads(keg_json)), kasus=kas, 
                                           nama_ci=n_ci, nip_ci=ci_data[0] if ci_data else "", ttd_ci=ci_data[1] if ci_data else None,
                                           nama_dosen=n_ds, nip_dosen=dsn_data[0] if dsn_data else "", ttd_dosen=dsn_data[1] if dsn_data else None,
                                           komen_ci=km_ci, komen_dosen=km_ds)
                            merger.append(pdf_buf)
                        merged_buffer = BytesIO()
                        merger.write(merged_buffer); merged_buffer.seek(0)
                        
                        st.session_state['preview_pdf'] = merged_buffer
                        st.session_state['preview_filename'] = f"Rekap_Logbook.pdf"
                        st.rerun()
            else: st.info("Anda belum memiliki logbook tervalidasi yang dapat diekspor.")

    # ==========================================
    # DASHBOARD CI (PEMBIMBING KLINIK)
    # ==========================================
    elif st.session_state['role'] == "Pembimbing Klinik (CI)":
        menu_options = ["👤 Profil Data Pembimbing Klinik (CI)", "📝 Menu Verifikasi Logbook (CI)"]
        pilihan_menu = st.sidebar.radio("Navigasi Dashboard", menu_options, index=menu_options.index(st.session_state['menu_aktif']) if st.session_state['menu_aktif'] in menu_options else 0)
        st.session_state['menu_aktif'] = pilihan_menu 
        if st.sidebar.button("Keluar (Logout)"): st.session_state.clear(); st.rerun()

        if pilihan_menu == "👤 Profil Data Pembimbing Klinik (CI)":
            st.title("👤 Profil Data Pembimbing Klinik (CI)")
            c.execute("SELECT nama, nim_nip, ttd_image FROM users WHERE id=?", (st.session_state['user_id'],))
            data_profil = c.fetchone()
            
            with st.form("profil_ci"):
                nama_baru = st.text_input("Nama Lengkap", value=data_profil[0])
                nip_baru = st.text_input("NIP/NIK", value=data_profil[1])
                st.markdown("**Unggah Tanda Tangan Digital**")
                if data_profil[2]: st.success("✓ Anda sudah mengunggah Tanda Tangan Digital.")
                else: st.warning("⚠ Anda belum mengunggah Tanda Tangan Digital.")
                
                ttd_file = st.file_uploader("Pilih file tanda tangan/TTD  (Maksimal 1 file, ukuran maks 2MB, format PNG transparan disarankan)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=False)
                
                if st.form_submit_button("Simpan Profil & TTD"):
                    c.execute('SELECT id FROM users WHERE nama=? AND id!=?', (nama_baru, st.session_state['user_id']))
                    nama_terpakai = c.fetchone()
                    
                    if nama_terpakai:
                        st.error("❌ Gagal update: Nama Lengkap tersebut sudah terdaftar pada pengguna lain!")
                    elif ttd_file and ttd_file.size > 2 * 1024 * 1024:
                        st.error("Gagal: Ukuran file gambar melebih 2MB. Silakan perkecil ukuran gambar Anda.")
                    else:
                        ttd_base64 = data_profil[2]
                        if ttd_file: ttd_base64 = base64.b64encode(ttd_file.read()).decode('utf-8')
                        c.execute("UPDATE users SET nama=?, nim_nip=?, ttd_image=? WHERE id=?", (nama_baru, nip_baru, ttd_base64, st.session_state['user_id']))
                        conn.commit()
                        st.session_state['nama'], st.session_state['nim_nip'] = nama_baru, nip_baru
                        st.success("Profil dan Tanda Tangan berhasil disimpan!")

        elif pilihan_menu == "📝 Menu Verifikasi Logbook (CI)":
            st.title("📝 Menu Verifikasi Logbook (CI)")
            
            c.execute("SELECT ttd_image, nim_nip FROM users WHERE id=?", (st.session_state['user_id'],))
            ci_info = c.fetchone()
            
            query_ci = """SELECT l.id, u.nama, u.nim_nip, l.tanggal, l.created_at, l.matkul, l.ruangan, l.hari_ke, l.kegiatan_json, l.kasus, l.nama_dosen_terpilih, l.status, l.komen_ci, l.komen_dosen 
                          FROM logbooks l JOIN users u ON l.user_id = u.id 
                          WHERE l.status IN ('Menunggu CI', 'Menunggu Dosen', 'Selesai') AND l.nama_ci_terpilih=? ORDER BY l.created_at DESC"""
            c.execute(query_ci, (st.session_state['nama'],))
            tugas_ci = c.fetchall()
            
            if len(tugas_ci) > 0:
                for i, row in enumerate(tugas_ci):
                    l_id, m_nama, m_nim, tgl, waktu_kirim, mk, rg, hk, k_json, kas, nd, stat, existing_komen, existing_kdosen = row
                    sudah_valid = stat != 'Menunggu CI'
                    
                    with st.expander(f"📁 [{stat}] {i+1}. Mahasiswa: {m_nama} | Matkul: {mk} ({tgl})"):
                        st.markdown(f"**NIM:** {m_nim} | **Ruangan:** {rg} | **Hari Ke-:** {hk}")
                        
                        pdf_buf = generate_pdf(m_nama, m_nim, tgl, mk, rg, hk, pd.DataFrame(json.loads(k_json)), kasus=kas, nama_ci=st.session_state['nama'], nip_ci=ci_info[1], ttd_ci=ci_info[0], komen_ci=existing_komen, komen_dosen=existing_kdosen)
                        if st.button("👁️ Tinjau Lembar PDF", key=f"btn_ci_p_{l_id}"):
                            st.session_state['preview_pdf'] = pdf_buf
                            st.session_state['preview_filename'] = f"Draft_{m_nama}.pdf"
                            st.rerun()
                        
                        komen_ci_input = st.text_area("Tambahkan Komentar/Catatan untuk Mahasiswa:", value=existing_komen if existing_komen else "", disabled=sudah_valid, key=f"txt_ci_{l_id}")
                        is_valid = st.checkbox("Saya menyatakan data logbook ini valid", value=sudah_valid, disabled=sudah_valid, key=f"val_{l_id}")
                        st.markdown(f"**Dosen Tujuan Penerusan:** {nd}")
                        
                        if stat == 'Menunggu CI':
                            if st.button("Validasi & Teruskan ke Dosen ➔", type="primary", key=f"kirim_{l_id}"):
                                if not is_valid: st.error("Anda harus menyetujui pernyataan validasi!")
                                else:
                                    c.execute("UPDATE logbooks SET status='Menunggu Dosen', komen_ci=? WHERE id=?", (komen_ci_input, l_id))
                                    conn.commit(); st.success("Logbook berhasil diteruskan!"); st.rerun()
                        elif stat == 'Menunggu Dosen':
                            if st.button("Batal Validasi & Tarik Berkas ✖", key=f"btl_ci_{l_id}"):
                                c.execute("UPDATE logbooks SET status='Menunggu CI' WHERE id=?", (l_id,)); conn.commit(); st.rerun()
                        else:
                            st.success("Logbook telah diselesaikan pada tingkat verifikasi akhir.")
            else: st.info("Belum ada logbook mahasiswa yang masuk.")

    # ==========================================
    # DASHBOARD DOSEN
    # ==========================================
    elif st.session_state['role'] == "Dosen":
        menu_options = ["👤 Profil Data Dosen", "🎓 Menu Verifikasi Akhir (Dosen)"]
        pilihan_menu = st.sidebar.radio("Navigasi Dashboard", menu_options, index=menu_options.index(st.session_state['menu_aktif']) if st.session_state['menu_aktif'] in menu_options else 0)
        st.session_state['menu_aktif'] = pilihan_menu 
        if st.sidebar.button("Keluar (Logout)"): st.session_state.clear(); st.rerun()

        if pilihan_menu == "👤 Profil Data Dosen":
            st.title("👤 Profil Data Dosen")
            c.execute("SELECT nama, nim_nip, ttd_image FROM users WHERE id=?", (st.session_state['user_id'],))
            data_profil = c.fetchone()
            
            with st.form("profil_dsn"):
                nama_baru = st.text_input("Nama Lengkap", value=data_profil[0])
                nip_baru = st.text_input("NIP/NIK", value=data_profil[1])
                st.markdown("**Unggah Tanda Tangan Digital**")
                if data_profil[2]: st.success("✓ Tanda Tangan Digital telah tersimpan.")
                else: st.warning("⚠ Anda belum mengunggah Tanda Tangan Digital.")
                
                ttd_file = st.file_uploader("Pilih File Gambar TTD (Maksimal 1 file, ukuran maks 2MB, format PNG transparan disarankan)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=False)
                
                if st.form_submit_button("Simpan Profil & TTD"):
                    c.execute('SELECT id FROM users WHERE nama=? AND id!=?', (nama_baru, st.session_state['user_id']))
                    nama_terpakai = c.fetchone()
                    
                    if nama_terpakai:
                        st.error("❌ Gagal update: Nama Lengkap tersebut sudah terdaftar pada pengguna lain!")
                    elif ttd_file and ttd_file.size > 2 * 1024 * 1024:
                        st.error("Gagal: Ukuran file gambar melebih 2MB. Silakan perkecil ukuran gambar Anda.")
                    else:
                        ttd_base64 = data_profil[2]
                        if ttd_file: ttd_base64 = base64.b64encode(ttd_file.read()).decode('utf-8')
                        c.execute("UPDATE users SET nama=?, nim_nip=?, ttd_image=? WHERE id=?", (nama_baru, nip_baru, ttd_base64, st.session_state['user_id']))
                        conn.commit()
                        st.session_state['nama'], st.session_state['nim_nip'] = nama_baru, nip_baru
                        st.success("Profil dan Tanda Tangan berhasil disimpan!")

        elif pilihan_menu == "🎓 Menu Verifikasi Akhir (Dosen)":
            st.title("🎓 Menu Verifikasi Akhir (Dosen)")
            
            c.execute("SELECT ttd_image, nim_nip FROM users WHERE id=?", (st.session_state['user_id'],))
            dsn_info = c.fetchone()
            
            query_dosen = """SELECT l.id, u.nama, u.nim_nip, l.tanggal, l.created_at, l.matkul, l.ruangan, l.hari_ke, l.kegiatan_json, l.kasus, l.nama_ci_terpilih, l.status, l.komen_ci, l.komen_dosen 
                             FROM logbooks l JOIN users u ON l.user_id = u.id 
                             WHERE l.status IN ('Menunggu Dosen', 'Selesai') AND l.nama_dosen_terpilih=? ORDER BY l.created_at DESC"""
            c.execute(query_dosen, (st.session_state['nama'],))
            tugas_dosen = c.fetchall()
            
            if len(tugas_dosen) > 0:
                for i, row in enumerate(tugas_dosen):
                    l_id, m_nama, m_nim, tgl, waktu_kirim, mk, rg, hk, k_json, kas, nc, stat, existing_kci, existing_kdosen = row
                    sudah_selesai = stat == 'Selesai'
                    
                    with st.expander(f"📁 [{stat}] {i+1}. Berkas Mahasiswa: {m_nama} ({tgl})"):
                        st.write(f"**Mata Kuliah:** {mk} | **Pembimbing Klinik (CI):** {nc}")
                        
                        ci_data = get_user_data(nc, "Pembimbing Klinik (CI)")
                        
                        pdf_buf = generate_pdf(m_nama, m_nim, tgl, mk, rg, hk, pd.DataFrame(json.loads(k_json)), kasus=kas, 
                                           nama_ci=nc, nip_ci=ci_data[0] if ci_data else "", ttd_ci=ci_data[1] if ci_data else None,
                                           nama_dosen=st.session_state['nama'], nip_dosen=dsn_info[1], ttd_dosen=dsn_info[0],
                                           komen_ci=existing_kci, komen_dosen=existing_kdosen)
                        
                        if st.button("👁️ Tinjau Lembar Berkas TTD CI", key=f"btn_ds_p_{l_id}"):
                            st.session_state['preview_pdf'] = pdf_buf
                            st.session_state['preview_filename'] = f"Akhir_{m_nama}.pdf"
                            st.rerun()
                            
                        komen_dosen_input = st.text_area("Tambahkan Komentar/Catatan untuk Mahasiswa:", value=existing_kdosen if existing_kdosen else "", disabled=sudah_selesai, key=f"txt_dsn_{l_id}")
                        is_valid = st.checkbox("Saya menyatakan data logbook ini valid", value=sudah_selesai, disabled=sudah_selesai, key=f"val_ds_{l_id}")
                        
                        if stat == 'Menunggu Dosen':
                            if st.button("Finalisasi & Tanda Tangani Berkas ➔", type="primary", key=f"fin_{l_id}"):
                                if not is_valid: st.error("Ceklis persetujuan validasi terlebih dahulu!")
                                else:
                                    c.execute("UPDATE logbooks SET status='Selesai', komen_dosen=? WHERE id=?", (komen_dosen_input, l_id))
                                    conn.commit(); st.success("Logbook selesai divalidasi penuh!"); st.rerun()
                        elif stat == 'Selesai':
                            if st.button("Batal Finalisasi Akhir ✖", key=f"btl_ds_{l_id}"):
                                c.execute("UPDATE logbooks SET status='Menunggu Dosen' WHERE id=?", (l_id,)); conn.commit(); st.rerun()
            else: st.info("Belum ada logbook tahap akhir yang masuk.")

    # ==========================================
    # GLOBAL: WINDOW PREVIEW PDF (BLOB OBJECT URL - AUTOMATIC ANTI-RELOAD)
    # ==========================================
    if st.session_state.get('preview_pdf') is not None:
        st.markdown("---")
        st.subheader("👁️ Kontrol Dokumen")
        
        col1, col2, col3 = st.columns([1.5, 1.5, 4])
        
        pdf_bytes = st.session_state['preview_pdf'].getvalue()
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        
        with col1:
            st.download_button("📥 Unduh (.pdf)", data=pdf_bytes, file_name=st.session_state['preview_filename'], type="primary")
        
        with col2:
            html_script_tab = f"""
            <script>
            function bukaTabTanpaReload() {{
                var base64str = "{base64_pdf}";
                var byteCharacters = atob(base64str);
                var byteNumbers = new Array(byteCharacters.length);
                for (var i = 0; i < byteCharacters.length; i++) {{
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }}
                var byteArray = new Uint8Array(byteNumbers);
                var file = new Blob([byteArray], {{type: 'application/pdf'}});
                var fileURL = URL.createObjectURL(file);
                window.open(fileURL, "_blank");
            }}
            </script>
            <button onclick="bukaTabTanpaReload()" style="background-color: #03a9f4; color: white; padding: 0.5rem 1rem; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; height: 38px;">
                🔗 Buka di Tab Baru
            </button>
            """
            st.components.v1.html(html_script_tab, height=45)
            
        with col3:
            if st.button("✖ Tutup Kontrol", key="tutup_preview_global"):
                st.session_state['preview_pdf'] = None
                st.rerun()
                
        st.info("💡 **Petunjuk:** Klik tombol **🔗 Buka di Tab Baru** untuk membuka dan melihat lembar cetak logbook secara utuh tanpa hambatan sistem.")

        
# streamlit run app7.py
