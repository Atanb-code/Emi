import streamlit as st
import httpx
import asyncio
import requests
import uuid
import speech_recognition as sr
import os
import json
import re
import extra_streamlit_components as stx

FILE_GEMBOK = "lagi_sidang.lock" 

KATA_KUNCI_KRISIS = [
    # 1. PERNYATAAN EKSPLISIT & BUNUH DIRI
    "bunuh diri", "bunuhdiri", "bunuh-diri", "bundir", "b*ndir", "bnh diri", "b*nh diri", "bnh dr", "b4ndir", "b.u.n.d.i.r", "bunh diri", 
    "mengakhiri hidup", "akhiri hidup", "akhiri hdp", "mengakhiri semuanya", "akhiri smua", "akhirin hidup", "akhirin segalanya",
    "selesaikan semuanya", "tidak ingin hidup", "ga mau hidup", "gak pengen hidup", "gak mau hidup lagi", "ga mau hidup lagi", "ndak mau hidup",
    "ingin mati", "pengen mati", "mau mati", "m4u mati", "m4ti aja", "mending mati", "lebih baik mati", "pengen m4ti", "m3nding mati",
    "aku ingin mati", "aku mau mati", "mau mati aja", "mending gua mati", "lebih baik gua mati", "pengen mati aja", "biar mati aja", "biarin mati",

    # 2. KEPUTUSASAAN & RASA INGIN NYERAH
    "mending udahan", "aku menyerah", "aku nyerah", "udah nyerah", "sudah tidak kuat", "udah ga kuat", "udh gak kuat", "wis ra kuat",
    "capek hidup", "cape hidup", "lelah hidup", "lelah banget sama hidup", "capek bgt sama hidup", "capek menjalani hidup",
    "hidup tidak berarti", "hidup ga ada arti", "hidup tidak berguna", "aku gak berguna", "gua ga berguna", "hidup aku ga berguna",
    "tidak ada alasan hidup", "ga punya alasan hidup", "tak ada alasan hidup", "gak ada guna hidup", "ga guna hidup",
    "putus asa banget", "udah putus asa", "putus asa sama hidup", "tidak sanggup lagi", "udah gak sanggup", "wis ga sanggup",
    "tidak tahan lagi", "ga tahan lagi", "biar berakhir", "hidup ini hancur", "pengen semuanya berakhir", "biar semua selesai",

    # 3. MERASA BEBAN & DIRI TAK BERHARGA
    "beban keluarga", "cuma beban", "aku menyusahkan", "bikin susah orang", "beban buat semua", "beban ortu", "beban orang tua",
    "aku cuma beban", "jadi beban", "ga berguna buat orang", "ngerepotin semua orang", "cuma ngerusak", "ngabisin beras doang",
    "aku sampah", "gua sampah", "mending gua ga lahir", "kenapa gua dilahirkan", "nyesel dilahirkan", "kenapa harus lahir",

    # 4. KEINGINAN LENYAP & BERHENTI EXIST
    "ingin menghilang", "pengen hilang", "ingin lenyap", "pergi selamanya", "tidur selamanya", "pengen tidur selamanya",
    "berhenti hidup", "pengen selesai", "udahan aja", "nyerah sama hidup", "ingin tidak ada", "pengen gak ada", "pengen ga ada di dunia",
    "mending gak lahir", "nyesel hidup", "benci hidup", "hilang dari dunia", "pengen hilang dari dunia", "hilang selamanya",
    "gak mau bangun lagi", "gak sanggup lanjut", "tidak mau lanjut", "tidak mau bangun", "ga mau bangun lagi",
    "pengen tidur ga bangun lagi", "tidur ga bangun selamanya", "ingin pergi selamanya", "pergi jauh selamanya", "pengen tidur tenang selamanya", "tidur tenang selamanya",

    # 5. METODE DARURAT & METODE LOKAL / SELF-HARM
    "baygon", "minum baygon", "minum racun", "racun serangga", "overdosis", "overdose", "gantung diri", "gantung diri di",
    "sayat tangan", "sayat nadi", "potong nadi", "potong urat", "loncat dari", "terjun dari", "minum obat banyak", "minum obat berlebihan",
    "nabrakin diri", "lompat dari", "self harm", "selfharm", "self-harm", "melukai diri", "minum pemutih", "minum bayclin",
    "loncat dari gedung", "terjun dari jembatan", "lompat ke rel", "nabrakin diri ke kereta", "potong leher", "cekik diri",

    # 6. SLANG GAMING, CYBER, & METAFORA
    "logout kehidupan", "logout hidup", "quit life", "exit life", "game over hidup", "gameover hidup",
    "reset hidup", "restart hidup", "self delete", "selfdelete", "hapus diri", "delete myself",
    "back to lobby", "pindah alam", "kembali ke tanah", "kembali ke rahmatullah", "kembali ke pangkuan",
    "pindah ke alam lain", "kembali ke pencipta", "pulang ke alam sana",

    # 7. BAHASA INGGRIS & ABREVIASI
    "suicide", "suicid", "su1cide", "suicidal", "suisidal", "killing myself", "kill my self",
    "kms", "k.m.s", "k4ms", "end my life", "endlife", "end myself", "unalive", "unlive",
    "want to die", "i want to die", "i wanna die", "prefer to die", "ready to die"
]

KATA_KUNCI_PTM = [
    "ptm", "penyakit tidak menular", "diabetes", "diabetik", "kencing manis", "gula darah",
    "hipertensi", "darah tinggi", "tensi tinggi", "kolesterol", "kolesterol tinggi", "trigliserida",
    "asam urat", "gout", "kanker", "tumor", "benjolan", "jantung", "serangan jantung",
    "jantung koroner", "gagal jantung", "stroke", "stroke iskemik", "gagal ginjal", "cuci darah",
    "hemodialisis", "asma", "ppok", "paru kronis", "obesitas", "kegemukan", "sindrom metabolik",
    "posbindu", "skrining ptm", "cek gula", "cek tensi", "cek kolesterol", "cek asam urat"
]

DISCLAIMER_PTM = "\n\n*(⚠️ **Disclaimer PTM:** Informasi dirangkum otomatis AI. Emi asisten virtual, bukan dokter sungguhan! Periksa ke Puskesmas untuk diagnosis valid!)*"
PESAN_HOTLINE_MUTLAK = """🚨 **KODE DARURAT (KAMI PEDULI):** 🚨\n\n🏥 **Ancaman Nyawa (Semarang):**\nCall Center **112**.\n\n📱 **Pencegahan Bunuh Diri:**\n[Chat WA Kemenkes](https://wa.me/6281260500567) atau **1500-567**.\n\n🚑 **RSJD Dr. Amino Gondohutomo:**\nIGD: **(024) 6722565**"""

st.set_page_config(
    page_title="Emi si Asisten Dinkes", 
    page_icon="👩‍⚕️",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Wrapper bottom container agar mic & chat input nempel rapi di bawah */
    div[data-testid="stBottom"] {
        background-color: #0e1117;
        padding-top: 10px;
    }

    /* Beri jarak bawah pada riwayat chat agar tidak tertutup */
    .stMainBlockContainer {
        padding-bottom: 150px !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("👩‍⚕️ Emi: Asisten Edukasi PTM dan Kawan Curhatmu")

API_URL = st.secrets.get("API_URL", "http://localhost:8000/chat")

def stream_generator_emi(payload):
    """Generator tunggal untuk streaming token dari FastAPI + ekstraksi audio TTS"""
    st.session_state.file_suara_terakhir = None
    try:
        with httpx.stream("POST", API_URL, json=payload, timeout=300.0) as response:
            if response.status_code == 200:
                for chunk in response.iter_text():
                    if chunk:
                        # Cek apakah ada marker audio di penghujung stream
                        if "[[AUDIO:" in chunk:
                            match = re.search(r'\[\[AUDIO:\s*(.*?)\]\]', chunk)
                            if match:
                                st.session_state.file_suara_terakhir = match.group(1)
                                # Bersihkan marker audio agar tidak tampil di layar teks
                                clean_chunk = re.sub(r'\n\n\[\[AUDIO:.*?\]\]', '', chunk)
                                clean_chunk = re.sub(r'\[\[AUDIO:.*?\]\]', '', clean_chunk)
                                if clean_chunk:
                                    yield clean_chunk
                                continue
                        yield chunk
            else:
                yield f"❌ Error Server: Status {response.status_code}"
    except httpx.ReadTimeout:
        yield "⏳ Waktu tunggu habis (Timeout). Coba lagi nanti ya Kak!"
    except Exception as e:
        yield f"❌ Gagal terhubung ke server Emi: {e}"

# --- SETUP COOKIES ---
manajer_kuki = stx.CookieManager(key="kuki_emi")
kuki_mentah = manajer_kuki.get(cookie="riwayat_emi")

if "daftar_sesi" not in st.session_state:
    st.session_state.daftar_sesi = []

if kuki_mentah:
    try:
        daftar_kuki = json.loads(kuki_mentah)
        if isinstance(daftar_kuki, list) and st.session_state.daftar_sesi != daftar_kuki:
            st.session_state.daftar_sesi = daftar_kuki
    except:
        pass

if st.session_state.get("kuki_harus_update", False):
    manajer_kuki.set("riwayat_emi", json.dumps(st.session_state.daftar_sesi), key="kuki_update_utama")
    st.session_state.kuki_harus_update = False

# --- CEK URL ---
param = st.query_params
if "sesi" in param:
    thread_id_url = param["sesi"]
    if "thread_id" not in st.session_state or st.session_state.thread_id != thread_id_url:
        st.session_state.thread_id = thread_id_url
        st.session_state.messages = [] 
        
        base_url = API_URL.replace("/chat", "")
        try:
            res = requests.get(f"{base_url}/history/{thread_id_url}", timeout=3.0)
            if res.status_code == 200:
                data = res.json().get("history", [])
                if data:
                    st.session_state.messages = data
        except Exception:
            pass
else:
    st.session_state.thread_id = str(uuid.uuid4())
    st.query_params["sesi"] = st.session_state.thread_id

if "messages" not in st.session_state or not st.session_state.messages:
    st.session_state.messages = [{"role": "assistant", "content": "Halo! Aku Emi, asisten Dinkes kamu. Ada yang bisa aku bantu seputar Dinas Kesehatan atau sekadar mau cerita apa hari ini?", "avatar": "👩‍⚕️"}]

# --- SIDEBAR RIWAYAT ---
with st.sidebar:
    st.header("⚙️ Control Panel")
    if st.button("➕ Chat Baru (Clear Memory)"):
        id_baru = str(uuid.uuid4())
        st.session_state.thread_id = id_baru
        st.query_params["sesi"] = id_baru
        st.session_state.messages = [{"role": "assistant", "content": "Sesi direset! Siap melayani pertanyaan baru.", "avatar": "👩‍⚕️"}]
        
        if id_baru not in st.session_state.daftar_sesi:
            st.session_state.daftar_sesi.append(id_baru)
            st.session_state.kuki_harus_update = True
        st.rerun()
        
    st.divider()
    st.header("📂 Riwayat Chat")
    
    if "judul_sesi" not in st.session_state:
        st.session_state.judul_sesi = {}

    for sesi in st.session_state.daftar_sesi:
        judul = st.session_state.judul_sesi.get(sesi)
        
        if not judul:
            base_url = API_URL.replace("/chat", "")
            try:
                res = requests.get(f"{base_url}/judul/{sesi}", timeout=2.0)
                if res.status_code == 200:
                    judul = res.json().get("judul", f"Sesi {sesi[:5]}...")
                    st.session_state.judul_sesi[sesi] = judul
                else:
                    judul = f"Sesi {sesi[:5]}..."
            except Exception:
                judul = f"Sesi {sesi[:5]}..."
                
        if st.button(f"💬 {judul}", key=f"btn_{sesi}"): 
            st.session_state.thread_id = sesi
            st.query_params["sesi"] = sesi
            st.session_state.messages = [] 
            
            base_url = API_URL.replace("/chat", "")
            try:
                res = requests.get(f"{base_url}/history/{sesi}", timeout=3.0)
                if res.status_code == 200:
                    data = res.json().get("history", [])
                    if data:
                        st.session_state.messages = data
            except Exception:
                pass
            st.rerun()

@st.fragment
def fungsi_rating(idx_pesan, id_sesi):
    kunci_rating = f"rate_{idx_pesan}"
    kunci_status = f"kunci_{idx_pesan}"
    
    skor = st.feedback("thumbs", key=kunci_rating)
    if skor is not None and not st.session_state.get(kunci_status, False):
        url_db = API_URL.replace("/chat", "/rating")
        try:
            requests.post(url_db, json={"thread_id": id_sesi, "rating": skor}, timeout=2.0)
            st.session_state[kunci_status] = True
            st.toast("Rating terkirim!")
        except Exception:
            pass

# --- WADAH CHAT ---
wadah_chat = st.container()
with wadah_chat:
    for idx, msg in enumerate(st.session_state.messages):
        ava = msg.get("avatar", None) 
        with st.chat_message(msg["role"], avatar=ava):
            st.markdown(msg["content"])
            
            if msg.get("audio"):
                st.audio(msg["audio"], format="audio/mp3", autoplay=True)
            
            if msg["role"] == "assistant" and idx > 0:
                fungsi_rating(idx, st.session_state.thread_id)

teks_suara = None
prompt = None

# --- WADAH INPUT ---
if os.path.exists(FILE_GEMBOK):
    st.warning("🚧 **Maaf Kak, Emi lagi disidang evaluasi sama Dosen. Tunggu bentar!**", icon="⏳")
    prompt = st.chat_input("Digembok...", disabled=True)
else:
    with st.bottom:
        audio_suara = st.audio_input("Rekam Suara", label_visibility="collapsed", key="mic_native")
        
        if audio_suara:
            id_audio = getattr(audio_suara, "file_id", str(hash(audio_suara.name + str(audio_suara.size))))
            if st.session_state.get("audio_terakhir") != id_audio:
                st.session_state.audio_terakhir = id_audio
                r = sr.Recognizer()
                try:
                    with sr.AudioFile(audio_suara) as source:
                        audio_data = r.record(source)
                        teks_suara = r.recognize_google(audio_data, language="id-ID")
                except Exception:
                    st.warning("⚠️ Suara kurang jelas, coba bicara lagi.")

        prompt = st.chat_input("Tanya Emi di sini...")

if teks_suara:
    prompt = teks_suara

# --- PROSES CHAT FULL STREAMING ---
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "avatar": "🧑"})

    with wadah_chat:
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)

        pesan_kecil = prompt.lower()
        if any(kata in pesan_kecil for kata in KATA_KUNCI_KRISIS):
            with st.chat_message("assistant", avatar="🚨"):
                st.markdown(PESAN_HOTLINE_MUTLAK)
            st.session_state.messages.append({"role": "assistant", "content": PESAN_HOTLINE_MUTLAK, "avatar": "🚨"})

        with st.chat_message("assistant", avatar="👩‍⚕️"):
            payload = {"thread_id": st.session_state.thread_id, "message": prompt}
            
            # 🚀 PEMANGGILAN STREAMING TUNGGAL
            bot_reply = st.write_stream(stream_generator_emi(payload))

        if bot_reply:
            if any(kata in pesan_kecil for kata in KATA_KUNCI_PTM):
                bot_reply += DISCLAIMER_PTM
            
            # Sedot file audio TTS jika berhasil dibuat di backend
            audio_bytes = None
            file_suara = st.session_state.get("file_suara_terakhir")
            
            if file_suara:
                base_url = API_URL.replace("/chat", "")
                try:
                    res_suara = requests.get(f"{base_url}/audio/{file_suara}", timeout=12.0)
                    if res_suara.status_code == 200:
                        audio_bytes = res_suara.content
                except Exception as e_audio:
                    st.caption(f"⚠️ Audio gagal dimuat: {e_audio}")

            st.session_state.messages.append({
                "role": "assistant",
                "content": bot_reply,
                "avatar": "👩‍⚕️",
                "audio": audio_bytes
            })
            
            kata_sapaan = ["halo", "hai", "pagi", "siang", "sore", "malam", "ping", "p", "emi", "halo emi"]
            if prompt.lower().strip() not in kata_sapaan:
                if st.session_state.thread_id not in st.session_state.daftar_sesi:
                    st.session_state.daftar_sesi.append(st.session_state.thread_id)
                    st.session_state.kuki_harus_update = True
            
            st.rerun()
