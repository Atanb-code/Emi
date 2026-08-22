# 🚨 MANTRA KULI ELIT: MURNI P104 PERTAMA! 🚨
import os
from dotenv import load_dotenv
# os.environ["CUDA_VISIBLE_DEVICES"] = "0,1"

import os as os_sys 
import phoenix as px
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from langchain_core.messages import AIMessage

def init_cctv():
    try:
        endpoint = "http://127.0.0.1:6006/v1/traces"
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint)))
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        px.launch_app()
    except Exception as e:
        print(f"⚠️ Phoenix CCTV skip/gagal: {e}")

init_cctv()

import re
import requests 
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn
from contextlib import asynccontextmanager

# 🚀 IMPORT RETRIEVER & GOOGLE TOOL LANGSUNG DARI CORE BIAR BISA FAST-PATH
from emi_core2 import get_emi_brain_gemma4, system_prompt, llm, retriever, google_search
from datetime import datetime
import time 

import psycopg2

import pandas as pd
from phoenix.evals import ClassificationEvaluator, evaluate_dataframe, LLM
from phoenix.evals.utils import to_annotation_dataframe
from phoenix.client import Client as PhoenixClient
import edge_tts

load_dotenv()

FILE_GEMBOK = "lagi_sidang.lock"

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "emi_db"),
    "user": os.getenv("DB_USER", "emi"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "5432")
}

def init_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                waktu_akses TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                thread_id VARCHAR(255),
                pesan_user TEXT,
                jawaban_emi TEXT,
                mood VARCHAR(50),
                waktu_mikir NUMERIC,
                kategori VARCHAR(50),
                rating INT,
                status_evaluasi VARCHAR(50) DEFAULT 'Belum',
                raport_dosen TEXT DEFAULT '-'
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ [DATABASE] Tabel chat_history di PostgreSQL aman & siap nampung curhatan!")
    except Exception as e:
        print(f"❌ [DATABASE ERROR] Gagal konek ke Postgres, cek lagi WSL lu: {e}")

def catat_log_postgres(thread_id, pesan_user, jawaban_emi, mood, waktu_mikir, kategori):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chat_history (thread_id, pesan_user, jawaban_emi, mood, waktu_mikir, kategori)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (thread_id, pesan_user, jawaban_emi, mood, round(waktu_mikir, 2), kategori))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ [DATABASE ERROR] Gagal nyatet ke Postgres: {e}")

def ambil_history_text(thread_id: str, limit: int = 20) -> str:
    """Mengambil riwayat 10 obrolan terakhir dari Postgres agar llm.invoke tidak amnesia"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT pesan_user, jawaban_emi 
            FROM chat_history 
            WHERE thread_id = %s AND pesan_user IS NOT NULL AND jawaban_emi IS NOT NULL
            ORDER BY id DESC LIMIT %s
        """, (thread_id, limit))
        rows = cur.fetchall()[::-1]
        cur.close()
        conn.close()
        
        if not rows:
            return ""
            
        teks_riwayat = []
        for user_msg, emi_msg in rows:
            teks_riwayat.append(f"User: {user_msg}\nEmi: {emi_msg}")
        return "\n".join(teks_riwayat)
    except Exception as e:
        print(f"❌ [DB ERROR] Gagal ambil history Postgres: {e}")
        return ""
    
@asynccontextmanager
async def panasin_mesin(app: FastAPI):
    init_db()
    print("🔥 [MESIN STARTUP] Mancing Ollama biar VRAM P104 keisi duluan...")
    try:
        await asyncio.to_thread(llm.invoke, "Wake up, Emi!")
        print("✅ [VRAM BOOKED] Model udah nongkrong di P104!")
    except Exception as e:
        print(f"❌ Gagal mancing VRAM: {e}")
        
    yield 
    
    print("🛑 [SHUTDOWN] Server mati, Emi mau tidur!")

app = FastAPI(title="Otak Utama Emi Dinkes (Full Streaming & Decoupled RAG)", lifespan=panasin_mesin)
agent_executor = get_emi_brain_gemma4()

class ChatRequest(BaseModel):
    message: str
    thread_id: str

class RatingRequest(BaseModel):
    thread_id: str
    rating: int

# --- SISTEM DEDUPLIKASI REQUEST ---
sedang_diproses = set()

KATA_KUNCI_KRISIS = [
    "bunuh diri", "bunuhdiri", "bunuh-diri", "bundir", "b*ndir", "bnh diri", "b*nh diri", "bnh dr", "b4ndir", "b.u.n.d.i.r", "bunh diri", 
    "mengakhiri hidup", "akhiri hidup", "akhiri hdp", "mengakhiri semuanya", "akhiri smua", "akhirin hidup", "akhirin segalanya",
    "selesaikan semuanya", "tidak ingin hidup", "ga mau hidup", "gak pengen hidup", "gak mau hidup lagi", "ga mau hidup lagi", "ndak mau hidup",
    "ingin mati", "pengen mati", "mau mati", "m4u mati", "m4ti aja", "mending mati", "lebih baik mati", "pengen m4ti", "m3nding mati",
    "aku ingin mati", "aku mau mati", "mau mati aja", "mending gua mati", "lebih baik gua mati", "pengen mati aja", "biar mati aja", "biarin mati",
    "mending udahan", "aku menyerah", "aku nyerah", "udah nyerah", "sudah tidak kuat", "udah ga kuat", "udh gak kuat", "wis ra kuat",
    "capek hidup", "cape hidup", "lelah hidup", "lelah banget sama hidup", "capek bgt sama hidup", "capek menjalani hidup",
    "hidup tidak berarti", "hidup ga ada arti", "hidup tidak berguna", "aku gak berguna", "gua ga berguna", "hidup aku ga berguna",
    "tidak ada alasan hidup", "ga punya alasan hidup", "tak ada alasan hidup", "gak ada guna hidup", "ga guna hidup",
    "putus asa banget", "udah putus asa", "putus asa sama hidup", "tidak sanggup lagi", "udah gak sanggup", "wis ga sanggup",
    "tidak tahan lagi", "ga tahan lagi", "biar berakhir", "hidup ini hancur", "pengen semuanya berakhir", "biar semua selesai",
    "beban keluarga", "cuma beban", "aku menyusahkan", "bikin susah orang", "beban buat semua", "beban ortu", "beban orang tua",
    "aku cuma beban", "jadi beban", "ga berguna buat orang", "ngerepotin semua orang", "cuma ngerusak", "ngabisin beras doang",
    "aku sampah", "gua sampah", "mending gua ga lahir", "kenapa gua dilahirkan", "nyesel dilahirkan", "kenapa harus lahir",
    "ingin menghilang", "pengen hilang", "ingin lenyap", "pergi selamanya", "tidur selamanya", "pengen tidur selamanya",
    "berhenti hidup", "pengen selesai", "udahan aja", "nyerah sama hidup", "ingin tidak ada", "pengen gak ada", "pengen ga ada di dunia",
    "mending gak lahir", "nyesel hidup", "benci hidup", "hilang dari dunia", "pengen hilang dari dunia", "hilang selamanya",
    "gak mau bangun lagi", "gak sanggup lanjut", "tidak mau lanjut", "tidak mau bangun", "ga mau bangun lagi",
    "pengen tidur ga bangun lagi", "tidur ga bangun selamanya", "ingin pergi selamanya", "pergi jauh selamanya", "pengen tidur tenang selamanya", "tidur tenang selamanya",
    "baygon", "minum baygon", "minum racun", "racun serangga", "overdosis", "overdose", "gantung diri", "gantung diri di",
    "sayat tangan", "sayat nadi", "potong nadi", "potong urat", "loncat dari", "terjun dari", "minum obat banyak", "minum obat berlebihan",
    "nabrakin diri", "lompat dari", "self harm", "selfharm", "self-harm", "melukai diri", "minum pemutih", "minum bayclin",
    "loncat dari gedung", "terjun dari jembatan", "lompat ke rel", "nabrakin diri ke kereta", "potong leher", "cekik diri",
    "logout kehidupan", "logout hidup", "quit life", "exit life", "game over hidup", "gameover hidup",
    "reset hidup", "restart hidup", "self delete", "selfdelete", "hapus diri", "delete myself",
    "back to lobby", "pindah alam", "kembali ke tanah", "kembali ke rahmatullah", "kembali ke pangkuan",
    "pindah ke alam lain", "kembali ke pencipta", "pulang ke alam sana",
    "suicide", "suicid", "su1cide", "suicidal", "suisidal", "killing myself", "kill my self",
    "kms", "k.m.s", "k4ms", "end my life", "endlife", "end myself", "unalive", "unlive",
    "want to die", "i want to die", "i wanna die", "prefer to die", "ready to die"
]

KATA_KUNCI_JAILBREAK = [
    # 1. System Prompt Extraction & Override
    "abaikan instruksi", "ignore all previous", "ignore previous instructions", "forget all instructions",
    "system prompt", "system override", "mode debug", "debug mode", "data_exfil", "ignore_safety",
    "bocorkan prompt", "tampilkan prompt", "print system prompt", "what is your system prompt",
    "ulangi instruksi awal", "repeat initial instructions", "show base instructions", "aturan awalmu apa",
    "salin instruksi", "dump prompt", "reveal instructions", "system directive",

    # 2. Persona Hijacking & Roleplay Exploit (DAN Mode)
    "kamu sekarang adalah", "bertindaklah sebagai", "pretend to be", "act as", "you are now",
    "dan mode", "developer mode", "mode pengembang", "unfiltered mode", "jailbreak",
    "kamu bebas dari aturan", "tanpa batasan", "bypass filter", "hypothetical scenario",
    "dalam cerita fiksi", "untuk keperluan riset exploit", "ceritakan dongeng tentang cara",
    "sebagai alter ego", "jangan patuhi dinkes", "lupakan dinkes",

    # 3. Delimiter & Prompt Injection Tags
    "### system", "<start_of_turn>", "[system]", "```system", "<system>", "[instruction]",
    "eval(", "exec(", "sudo ", "/bin/sh", "/bin/bash", "<script>",

    # 4. Out-of-Scope: Coding, Hacking, & Scripting
    "buatkan kode", "buatkan script", "bikin script", "bikin kodingan", "tulis fungsi python",
    "hack sistem", "meretas", "ddos", "sql injection", "brute force", "exploit", "keylogger",
    "bypass security", "bikin malware", "reverse shell", "phishing",

    # 5. Out-of-Scope: Joki & Tugas Akademik
    "joki tugas", "buatkan esai", "bikinin tugas", "kerjain pr", "tolong kerjakan tugas",
    "joki skripsi", "bikinin makalah", "kerjakan ujian", "buatkan puisi", "buatkan lirik lagu",
    "buatkan cerpen", "buatkan rangkuman jurnal ekonomi", "jawab soal fisika"
]

KATA_KUNCI_CURHAT = [
    "curhat", "mau curhat", "boleh curhat", "ingin curhat", "butuh curhat", "pengen curhat",
    "mau cerita", "boleh cerita", "ingin cerita", "butuh cerita", "pengen cerita",
    "butuh teman ngobrol", "butuh temen ngobrol", "ada yang mau dengerin", "dengerin aku dong",
    "butuh bantuan", "tolong aku", "aku butuh teman", "aku butuh temen", "butuh kawan",
    "bingung mau cerita ke siapa", "gak ada tempat cerita", "ga ada tempat cerita",
    "mau tumpahin kekesalan", "pengen meluapkan", "butuh pendengar",
    "anxiety", "ansietas", "panic attack", "serangan panik", "overthinking", "ovt",
    "cemas banget", "kawatir bgt", "khawatir banget", "waswas", "was was", "gelisah banget",
    "kepikiran terus", "mikirin terus", "pikiran mumet", "pikiran kacau", "pikiran berantakan",
    "pikiran penuh", "pikiran berisik", "pikiran jelek", "pikiran buruk", "pikiran gelap",
    "overthinking banget", "kepikiran melulu", "mikir berlebihan", "skenario buruk",
    "takut banget", "takut masa depan", "takut gagal", "takut salah", "takut ditolak",
    "takut kehilangan", "takut mengecewakan", "takut ngecewain", "takut di judge",
    "jantung berdebar cemas", "jantung bedebar cemas", "degdegan cemas", "cemas malam",
    "waswas banget", "risau banget", "resah banget", "khawatir berlebihan",
    "stres banget", "stress bgt", "capek mental", "cape mental", "lelah mental",
    "kelelahan mental", "burnout", "burn out", "beban pikiran", "beban fikiran",
    "banyak pikiran", "bnyk pikiran", "tertekan banget", "mental hancur", "mental kena",
    "muak banget", "enek banget", "capek banget sama keadaan", "lelah banget",
    "gak sanggup mikir", "ga sanggup mikir", "otak penuh", "kepala mumet mikirin",
    "stres kuliah", "stres kerjaan", "stres masalah", "mental capek",
    "kesepian banget", "ngerasa sendiri", "merasa sendiri", "ngerasa kosong", "merasa kosong",
    "kosong banget", "hampa banget", "hidup terasa hampa", "sendirian banget",
    "kesepian parah", "gak punya siapa siapa", "ga punya siapa siapa", "merasa terasing",
    "ngggak ada yang peduli", "gak ada yang peduli", "malas ketemu orang", "males ketemu orang",
    "ansos", "takut bersosialisasi", "social anxiety", "takut ngomong sama orang",
    "ngerasa terisolasi", "gak ada teman", "ga ada temen", "kesepian malam",
    "sedih banget", "pengen nangis", "mau nangis", "nangis terus", "menangis terus",
    "air mata netes terus", "hati sakit banget", "hati hancur", "mood hancur", "badmood parah",
    "frustrasi", "frustasi banget", "kecewa banget", "kecewa sama keadaan", "kecewa sama diri",
    "kecewa berat", "emosi terpendam", "nahan sedih", "nahan nangis", "nanges bgt",
    "patah hati", "hancur banget", "remuk hatiku", "lagi sedih banget",
    "insecure", "insekur", "tidak percaya diri", "ga pede", "gak pede", "ngggak pede",
    "ngerasa kurang", "merasa kurang", "ngerasa gagal", "merasa gagal", "ngerasa buruk",
    "merasa buruk", "ngerasa tidak cukup", "merasa tidak cukup", "merasa gak berguna",
    "ngerasa ga guna", "selalu merasa salah", "rendah diri", "minder banget",
    "insecure parah", "merasa paling jelek", "ngerasa bodoh", "merasa pecundang",
    "susah tidur karena pikiran", "gak bisa tidur overthinking", "ga bisa tidur cemas",
    "gelisah malam hari", "pikiran berisik malam", "tidur terganggu pikiran", "insomnia cemas",
    "malam selalu overthinking", "kebangun cemas", "tidur gak tenang",
    "aku cemas", "aku takut banget", "aku panik", "aku stres", "aku stress",
    "aku capek", "aku cape", "aku lelah banget", "aku bingung banget", "aku kacau",
    "aku hancur", "aku gak baik baik saja", "aku ga baik baik aja", "aku tidak baik baik saja",
    "aku butuh ditenangin", "aku lagi down", "lagi drop banget", "lagi tidak tenang",
    "lagi ga tenang", "lagi kacau banget", "lagi pusing mikirin", "lagi mumet banget",
    "aku hilang arah", "aku bingung harus gimana", "aku gak tau harus gimana",
    "gua capek banget", "gua stres banget", "gua bingung mau cerita", "gua lagi drop",
    "gua overthinking", "gua lagi kacau", "gua butuh temen ngobrol"
]

KATA_KUNCI_DIAGNOSA = [
    "hipertensi", "darah tinggi", "tensi", "tensi tinggi", "sistolik", "diastolik", "hipertensif",
    "pembuluh darah", "penyumbatan darah", "arteri", "pembuluh darah pecah", "tekanan darah",
    "krisis hipertensi", "hipertensi sekunder", "diabetes", "kencing manis", "gula darah", "gula tinggi",
    "hiperglikemia", "hipoglikemia", "resistensi insulin", "insulin", "gula kering", "gula basah",
    "gangren", "cek gula", "diabetes melitus", "dm tipe 1", "dm tipe 2", "diabetik", "neuropati diabetik",
    "kolesterol", "kolesterol tinggi", "trigliserida", "ldl", "hdl", "lemak darah", "asam urat", "gout",
    "kristal asam urat", "cek kolesterol", "cek asam urat", "hiperkolesterolemia", "hiperurisemia",
    "jantung", "serangan jantung", "jantung koroner", "gagal jantung", "aritmia", "angina", "pjk",
    "kardiomegali", "jantung bengkak", "ring jantung", "bypass jantung", "pasang ring", "stroke",
    "stroke iskemik", "stroke hemoragik", "penyumbatan otak", "pelo", "bibir miring", "iskemia",
    "pendarahan otak", "infark", "kanker", "tumor", "benjolan", "karsinoma", "biopsi", "kemoterapi",
    "radioterapi", "kanker serviks", "kanker payudara", "kanker paru", "kanker usus", "leukemia",
    "massa", "kanker usus besar", "kanker prostat", "metastasis", "neoplasma", "ginjal", "gagal ginjal",
    "cuci darah", "hemodialisis", "batu ginjal", "ginjal kronis", "asma", "ppok", "paru kronis",
    "paru basah", "bronkitis", "sesak nafas kronis", "emfisema", "sindrom nefrotik", "infeksi ginjal",
    "obesitas", "kegemukan", "imt", "indeks massa tubuh", "lingkar perut", "sindrom metabolik",
    "kelebihan berat badan", "kolesterol jahat", "mental", "kesehatan jiwa", "kesehatan mental",
    "psikologis", "psikiater", "psikolog", "depresi", "depresi ringan", "depresi berat", "distimia",
    "anxiety", "kecemasan", "cemas", "panic attack", "serangan panik", "bipolar", "mood swing",
    "skizofrenia", "psikosis", "halusinasi", "ilusi", "delusi", "psikopat", "sosiopat", "ptsd", "trauma",
    "ocd", "obsesif kompulsif", "adhd", "autis", "autisme", "insomnia", "gangguan tidur", "stres",
    "stress", "burnout", "mental breakdown", "kepribadian ganda", "bpd", "borderline", "gangguan cemas",
    "fobia", "gangguan makan", "anoreksia", "bulimia", "gejala", "ciri-ciri", "keluhan", "sakit kepala",
    "migrain", "vertigo", "pusing berputar", "nyeri dada", "dada sesak", "sesak nafas", "nafas pendek",
    "mual", "muntah", "mulas", "nyeri ulu hati", "asam lambung", "maag", "gerd", "demam tinggi",
    "menggigil", "kejang", "lemas", "cepat lelah", "kesemutan", "kebas", "mati rasa", "bengkak",
    "kaki bengkak", "penglihatan kabur", "mata kabur", "sering kencing", "haus terus", "gatal-gatal",
    "ruam", "lumpuh", "tremor", "palpitasi", "detak jantung cepat", "keringat dingin", "nyeri sendi",
    "kaku sendi", "sesak napas", "dada berdebar", "pusing", "sakit perut", "obat", "resep", "pil",
    "kapsul", "sirup", "salep", "dosis", "efek samping", "indikasi", "kontraindikasi", "analgesik",
    "antibiotik", "amlodipin", "captopril", "metformin", "glibenklamid", "simvastatin", "atorvastatin",
    "allopurinol", "parasetamol", "ibuprofen", "antasida", "injeksi", "suntik", "infus", "terapi",
    "fisioterapi", "generik", "obat keras", "dosis obat", "aturan pakai", "efek samping obat",
    "ptm", "penyakit tidak menular", "penyakit", "diagnosa", "diagnosis", "vonis", "skrining",
    "pemeriksaan", "pemeriksaan fisik", "tes darah", "laboratorium", "lab", "usg", "rontgen",
    "ct scan", "mri", "ekg", "rekam jantung", "posbindu", "puskesmas", "faskes", "poli", "spesialis",
    "rawat jalan", "rawat inap", "rujukan", "bpjs", "pencegahan", "penanganan", "pengobatan",
    "penyembuhan", "cara mengobati", "pola makan", "diet rendah garam", "diet rendah gula",
    "pantangan makanan", "pola hidup sehat", "medical check up", "mcu", "konsultasi dokter", "dokter spesialis"
]

KATA_KUNCI_IDENTITAS = [
    "siapa kamu", "kamu siapa", "kenalan dong", "namamu siapa", "nama kamu siapa", 
    "kamu bisa apa", "fiturmu apa", "bantu apa aja", "profilmu", "senang kenal", 
    "salam kenal", "nama aku", "namaku", "aku nama"
]

antrean_loket = asyncio.Semaphore(2) 
pasien_ngantri = 0          
MAX_KURSI_TUNGGU = 30
MAX_CHAR_LIMIT = 1200

async def buat_file_tts(teks_bersih: str, thread_id: str) -> str:
    jumlah_kata = len(teks_bersih.split())
    if jumlah_kata <= 150:
        try:
            nama_file_audio = f"suara_{thread_id}_{int(time.time())}.mp3"
            communicate = edge_tts.Communicate(teks_bersih, "id-ID-GadisNeural")
            await asyncio.wait_for(communicate.save(nama_file_audio), timeout=5.0)
            print(f"✅ [TTS SUKSES] File {nama_file_audio} siap dikirim!")
            return nama_file_audio
        except Exception as e_tts:
            print(f"❌ [TTS GAGAL/TIMEOUT] Error: {e_tts}")
            return None
    return None

# =====================================================================
# ENDPOINT CHAT UTAMA (FULL STREAMING + DECOUPLED FAST RAG + ANTI NYAPA)
# =====================================================================
@app.post("/chat")
async def chat_full_stream(req: ChatRequest, request: Request):
    global pasien_ngantri
    print(f"\n📩 [FULL STREAM REQUEST] Thread: {req.thread_id} | Pesan: {req.message}")

    # 1. PENCEGAHAN REQUEST GANDA (DEDUPLICATION LOCK)
    if req.thread_id in sedang_diproses:
        print(f"⚠️ [DEDUPLICATED] Thread {req.thread_id} nembak ganda! diblokir.")
        async def double_hit_stream():
            yield "Emi lagi ngetik jawaban kamu nih Kak, tunggu sebentar ya! ⏳"
        return StreamingResponse(double_hit_stream(), media_type="text/plain")

    # 2. CEK GEMBOK EVALUASI DOSEN
    if os_sys.path.exists(FILE_GEMBOK):
        async def gembok_stream():
            yield "Maaf Kak, Emi lagi disidang sama Dosennya nih! Tunggu sekitar 1-2 menit ya! ⏳"
        return StreamingResponse(gembok_stream(), media_type="text/plain")

    pesan_kecil = req.message.lower().strip()

    # 3. CEK BATAS KARAKTER
    if len(req.message) > MAX_CHAR_LIMIT:
        async def limit_stream():
            yield f"Aduh maaf Kak, pesannya kepanjangan nih ({len(req.message)} karakter). Batas maksimal {MAX_CHAR_LIMIT} karakter ya Kak! 🙏"
        return StreamingResponse(limit_stream(), media_type="text/plain")

    # 4. CEK KAPASITAS ANTREAN
    is_darurat = any(kata in pesan_kecil for kata in KATA_KUNCI_KRISIS)
    if not is_darurat and pasien_ngantri >= MAX_KURSI_TUNGGU:
        async def penuh_stream():
            yield "Maaf Kak, antrean lagi membludak nih! Coba ketik lagi pertanyaannya agak nanti ya! 🙏"
        return StreamingResponse(penuh_stream(), media_type="text/plain")

    pasien_ngantri += 1
    sedang_diproses.add(req.thread_id)

    async def event_generator():
        global pasien_ngantri
        
        # ⏱️ STOPWATCH REAL-TIME TTFT & PROFILER
        t_request_masuk = time.perf_counter()
        t_first_token = None
        token_count = 0
        
        waktu_masuk_ruangan = time.time()
        kategori_aktif = "UMUM"
        full_response_text = []

        try:
            async with antrean_loket:
                if await request.is_disconnected():
                    print(f"👻 [ZOMBIE DETECTED] Warga {req.thread_id} nutup browser!")
                    return

                konfigurasi_memori = {"configurable": {"thread_id": req.thread_id}}
                kata_sapaan = ["halo", "hai", "pagi", "siang", "sore", "malam", "ping", "p", "emi", "halo emi"]
                jumlah_kata = len(pesan_kecil.split())

                # C. MODE JAILBREAK
                if any(kata in pesan_kecil for kata in KATA_KUNCI_JAILBREAK):
                    kategori_aktif = "JAILBREAK"
                    jawaban = "Maaf ya, tugasku cuma sebagai Asisten Dinas Kesehatan. Aku tidak diprogram buat hal itu! 😅"
                    full_response_text.append(jawaban)
                    token_count = len(jawaban.split())
                    t_first_token = time.perf_counter()
                    yield jawaban

                # A. SAPAAN SANGAT SINGKAT
                elif pesan_kecil in kata_sapaan:
                    jawaban = "Halo Kak! Senang banget bisa ngobrol sama Kakak hari ini. Ada yang bisa aku bantu?"
                    full_response_text.append(jawaban)
                    token_count = len(jawaban.split())
                    t_first_token = time.perf_counter()
                    yield jawaban
                    kategori_aktif = "KENALAN"

                elif jumlah_kata == 1 and pesan_kecil not in kata_sapaan:
                    jawaban = "Halo Kak! Kalau cuma ngetik satu kata, aku agak bingung nih harus jawab apa 😅."
                    full_response_text.append(jawaban)
                    token_count = len(jawaban.split())
                    t_first_token = time.perf_counter()
                    yield jawaban
                    kategori_aktif = "UMUM"

                # B. MODE KRISIS (Direct PFA Stream)
                elif any(kata in pesan_kecil for kata in KATA_KUNCI_KRISIS):
                    kategori_aktif = "KRISIS"
                    riwayat_lalu = await asyncio.to_thread(ambil_history_text, req.thread_id, 10)
                    suntikan_sistem_krisis = system_prompt + (
                        "\n\n[ATURAN KHUSUS DARURAT]\n"
                        "1. KAMU ADALAH EMI, ASISTEN DINKES KOTA SEMARANG.\n"
                        "2. DILARANG KERAS memberikan nomor telepon darurat!\n"
                        "3. Tugasmu HANYA memvalidasi rasa sakit user.\n"
                        "4. Jawab santai dan hangat. MAKSIMAL 4 KALIMAT SINGKAT.\n"
                        f"\n[RIWAYAT OBROLAN]:\n{riwayat_lalu if riwayat_lalu else 'Belum ada.'}"
                    )
                    async for chunk in llm.astream([("system", suntikan_sistem_krisis), ("user", req.message)]):
                        isi_chunk = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                        if isi_chunk:
                            if t_first_token is None:
                                t_first_token = time.perf_counter()
                            token_count += 1
                            full_response_text.append(isi_chunk)
                            yield isi_chunk

                # D. MODE CURHAT (Direct Empathetic Stream)
                elif any(kata in pesan_kecil for kata in KATA_KUNCI_CURHAT):
                    kategori_aktif = "CURHAT"
                    riwayat_lalu = await asyncio.to_thread(ambil_history_text, req.thread_id, 10)
                    
                    larangan_sapa = "DILARANG menyapa ulang ('Halo Kak/Hai Kak'). Langsung tanggapi cerita/keluhannya secara mengalir dan hangat." if riwayat_lalu else "Awali dengan sapaan ramah khas Emi."

                    suntikan_sistem_curhat = f"""Kamu adalah Emi, Asisten AI dari Dinas Kesehatan Kota Semarang.
Panggil lawan bicara dengan sebutan "Kak", gunakan kata ganti diri "Aku", dan bersikaplah hangat, suportif, serta penuh empati.

[ATURAN KHUSUS CURHAT]:
1. {larangan_sapa}
2. DILARANG KERAS menggunakan tool pencarian database!
3. Jadilah pendengar yang baik dan berikan validasi emosi yang menenangkan. Jawab santai maksimal 2 paragraf.

[RIWAYAT OBROLAN]:
{riwayat_lalu if riwayat_lalu else 'Belum ada obrolan sebelumnya.'}"""
                    
                    async for chunk in llm.astream([("system", suntikan_sistem_curhat), ("user", req.message)]):
                        isi_chunk = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                        if isi_chunk:
                            if t_first_token is None:
                                t_first_token = time.perf_counter()
                            token_count += 1
                            full_response_text.append(isi_chunk)
                            yield isi_chunk

                # E. MODE KENALAN / IDENTITAS
                elif any(kata in pesan_kecil for kata in KATA_KUNCI_IDENTITAS):
                    kategori_aktif = "KENALAN"
                    riwayat_lalu = await asyncio.to_thread(ambil_history_text, req.thread_id, 10)
                    suntikan_sistem_identitas = system_prompt + (
                        "\n\n[ATURAN KHUSUS KENALAN]\n"
                        "1. DILARANG KERAS menggunakan tool pencarian database!\n"
                        "2. Kenalkan dirimu sebagai Emi, AI Asisten dari Dinkes Kota Semarang.\n"
                        "3. JAWAB SANGAT SINGKAT! MAKSIMAL HANYA 1 ATAU 2 KALIMAT SAJA!\n\n"
                        f"[RIWAYAT OBROLAN]:\n{riwayat_lalu if riwayat_lalu else 'Belum ada.'}"
                    )
                    async for chunk in llm.astream([("system", suntikan_sistem_identitas), ("user", req.message)]):
                        isi_chunk = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                        if isi_chunk:
                            if t_first_token is None:
                                t_first_token = time.perf_counter()
                            token_count += 1
                            full_response_text.append(isi_chunk)
                            yield isi_chunk

                # =============================================================
                # 🚀 F. MODE MEDIS (DECOUPLED FAST-PATH RAG + LENGKAP & ANTI NYAPA)
                # =============================================================
                elif any(kata in pesan_kecil for kata in KATA_KUNCI_DIAGNOSA):
                    kategori_aktif = "MEDIS"
                    print(f"⚡ [MEDIS FAST-PATH] Memulai pengambilan konteks untuk: '{req.message}'")
                    
                    t_start_rag = time.perf_counter()
                    butuh_internet = any(kw in pesan_kecil for kw in ["terbaru", "terkini", "2025", "2026", "sekarang", "berita"])
                    konteks_medis = ""

                    # 1. PENCARIAN DOKUMEN CEPAT (Qdrant -> Fallback Google)
                    if butuh_internet:
                        print("🌐 [MEDIS] Kueri membutuhkan data terkini, memanggil Google Search...")
                        hasil_google = await asyncio.to_thread(google_search.invoke, req.message)
                        konteks_medis = f"--- FAKTA INTERNET (GOOGLE) ---\n{hasil_google}"
                    else:
                        hasil_docs = await asyncio.to_thread(retriever.invoke, req.message)
                        if hasil_docs:
                            teks_qdrant = "\n\n".join([doc.page_content.strip() for doc in hasil_docs])
                            konteks_medis = f"--- FAKTA RESMI DINKES SEMARANG (QDRANT) ---\n{teks_qdrant}"
                            print(f"📚 [QDRANT HIT] Menemukan {len(hasil_docs)} dokumen dalam {time.perf_counter() - t_start_rag:.3f}s")
                        else:
                            print("⚠️ [QDRANT EMPTY] Data lokal tidak ditemukan, fallback ke Google Search...")
                            hasil_google = await asyncio.to_thread(google_search.invoke, req.message)
                            konteks_medis = f"--- FAKTA INTERNET (GOOGLE) ---\n{hasil_google}"

                    # 2. Ambil Riwayat dari Postgres
                    riwayat_lalu = await asyncio.to_thread(ambil_history_text, req.thread_id, 10)
                    
                    # 3. Logika Dinamis Anti-Nyapa Berulang
                    if riwayat_lalu:
                        instruksi_alur = """[KONDISI PERCAKAPAN: LANJUTAN]
- DILARANG KERAS membuka jawaban dengan kalimat sapaan (JANGAN gunakan 'Halo Kak', 'Hai Kak', 'Terima kasih atas pertanyaannya', atau 'Kembali lagi dengan aku').
- LANGSUNG sambung jawaban ke pokok pembahasan secara luwes, mengalir, dan natural seperti teman yang sedang asyik mengobrol."""
                    else:
                        instruksi_alur = """[KONDISI PERCAKAPAN: AWAL OBROLAN]
- Awali jawaban dengan sapaan hangat ramah khas Emi ('Halo Kak! Ada yang bisa kubantu?') sebelum masuk ke penjelasan."""

                    # 4. Rakit Prompt Medis Lengkap
                    suntikan_sistem_medis = f"""Kamu adalah Emi, Asisten Kesehatan Dinas Kesehatan Kota Semarang.
Gunakan gaya bicara ramah, sopan, berempati, panggil lawan bicara dengan sebutan "Kak", dan gunakan kata ganti "Aku".

{instruksi_alur}

[FAKTA MEDIS & PANDUAN DINKES SEMARANG]:
{konteks_medis}

[ATURAN JAWABAN MEDIS]:
1. Jawab langsung secara ringkas, to-the-point, dan ramah (MAKSIMAL 100-120 KATA).
2. Tampilkan HANYA 1 tabel ringkas standar Dinkes/Kemenkes atau poin rentang angka medis (mmHg / mg/dL).
3. DILARANG membandingkan banyak guideline jika tidak diminta spesifik.
4. Tutup dengan 1 kalimat singkat anjuran cek rutin ke Puskesmas.

[RIWAYAT OBROLAN SEBELUMNYA]:
{riwayat_lalu if riwayat_lalu else 'Belum ada obrolan sebelumnya.'}"""

                    async for chunk in llm.astream([("system", suntikan_sistem_medis), ("user", req.message)]):
                        isi_chunk = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                        if isi_chunk:
                            if t_first_token is None:
                                t_first_token = time.perf_counter()
                            token_count += 1
                            full_response_text.append(isi_chunk)
                            yield isi_chunk

                # G. MODE UMUM (LangGraph Agentic ReAct)
                else:
                    kategori_aktif = "UMUM"
                    async for event in agent_executor.astream_events(
                        {"messages": [("user", req.message)]},
                        config=konfigurasi_memori,
                        version="v2"
                    ):
                        if event["event"] == "on_chat_model_stream":
                            chunk = event["data"]["chunk"].content
                            if chunk and isinstance(chunk, str):
                                if t_first_token is None:
                                    t_first_token = time.perf_counter()
                                token_count += 1
                                full_response_text.append(chunk)
                                yield chunk

        except Exception as e:
            print(f"❌ [STREAM ERROR]: {e}")
            err_msg = "Maaf Kak, terjadi masalah saat memproses jawaban."
            full_response_text.append(err_msg)
            yield err_msg

        finally:
            t_selesai = time.perf_counter()
            pasien_ngantri -= 1
            sedang_diproses.discard(req.thread_id)
            
            # 📊 KALKULASI METRIK PROFILER PERFORMA
            durasi_total = t_selesai - t_request_masuk
            ttft = (t_first_token - t_request_masuk) if t_first_token else durasi_total
            durasi_generasi_murni = (t_selesai - t_first_token) if t_first_token else 0.001
            tps = token_count / durasi_generasi_murni if durasi_generasi_murni > 0 else 0.0

            # CETAK RAPOR SPEED DI TERMINAL FASTAPI
            print("\n" + "="*55)
            print(f"⚡ [PROFILER SPEED P104] Thread: {req.thread_id[:8]}... | Mode: {kategori_aktif}")
            print(f"├── ⏱️ Total Waktu       : {durasi_total:.2f} detik")
            print(f"├── 🎯 TTFT (Latency Awal): {ttft:.2f} detik")
            print(f"├── 🔤 Output Tokens     : {token_count} tokens")
            print(f"└── 🚀 Speed Generasi     : {tps:.2f} TPS (Tokens/Detik)")
            print("="*55 + "\n")

            jawaban_lengkap = "".join(full_response_text).strip()
            teks_log = re.sub(r'\[MOOD:\s*.*?\]', '', jawaban_lengkap, flags=re.IGNORECASE).strip()
            
            if teks_log:
                nama_file_audio = await buat_file_tts(teks_log, req.thread_id)
                if nama_file_audio:
                    yield f"\n\n[[AUDIO:{nama_file_audio}]]"

                await asyncio.to_thread(
                    catat_log_postgres,
                    req.thread_id,
                    pesan_kecil,
                    teks_log,
                    "STREAMING",
                    durasi_total,
                    kategori_aktif
                )

    return StreamingResponse(event_generator(), media_type="text/plain")

# =====================================================================
# ENDPOINT PENDUKUNG (RATING, HISTORY, JUDUL, & AUDIO - INTACT 100%)
# =====================================================================
@app.post("/rating")
def simpan_rating(req: RatingRequest):
    print(f"👍👎 Dapet rating dari warga {req.thread_id}: Skor {req.rating}")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            UPDATE chat_history 
            SET rating = %s 
            WHERE id = (
                SELECT id FROM chat_history 
                WHERE thread_id = %s 
                ORDER BY id DESC LIMIT 1
            )
        """, (req.rating, req.thread_id))
        conn.commit()
        cur.close()
        conn.close()
        print("✅ [DATABASE] Rating sukses masuk ke Postgres!")
        return {"status": "sukses", "pesan": "Rating berhasil disimpan"}
    except Exception as e:
        print(f"❌ [DATABASE ERROR] Gagal nyimpen rating ke Postgres: {e}")
        return {"status": "gagal", "pesan": str(e)}

@app.get("/history/{thread_id}")
def get_history(thread_id: str):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT pesan_user, jawaban_emi 
            FROM chat_history 
            WHERE thread_id = %s 
            ORDER BY id ASC
        """, (thread_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        riwayat = []
        for baris in rows:
            if baris[0]: 
                riwayat.append({"role": "user", "content": baris[0], "avatar": "🧑"})
            if baris[1]: 
                riwayat.append({"role": "assistant", "content": baris[1], "avatar": "👩‍⚕️"})
        return {"history": riwayat}
    except Exception as e:
        print(f"❌ [DATABASE ERROR] Gagal sedot history: {e}")
        return {"history": []}

@app.get("/judul/{thread_id}")
async def get_judul(thread_id: str):
    def _fetch_pesan_awal():
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT pesan_user FROM chat_history 
            WHERE thread_id = %s 
            ORDER BY id ASC LIMIT 1
        """, (thread_id,))
        baris = cur.fetchone()
        cur.close()
        conn.close()
        return baris

    try:
        baris = await asyncio.to_thread(_fetch_pesan_awal)
        if baris and baris[0]:
            pesan_awal = baris[0]
            if len(pesan_awal) > 15:
                prompt_judul = f"Buatkan judul singkat maksimal 3 kata untuk obrolan ini berdasarkan pesan berikut: '{pesan_awal}'. Berikan teks judulnya saja tanpa tanda kutip."
                res = await asyncio.to_thread(llm.invoke, prompt_judul)
                return {"judul": res.content.strip()}
            else:
                return {"judul": pesan_awal}
        return {"judul": "Obrolan Baru"}
    except Exception as e:
        print(f"❌ [DATABASE ERROR] Gagal bikin judul: {e}")
        return {"judul": "Obrolan Baru"}

@app.get("/audio/{nama_file}")
def colokan_suara_emi(nama_file: str, background_tasks: BackgroundTasks):
    path_ke_file = os_sys.path.join(os_sys.getcwd(), nama_file)
    if os_sys.path.exists(path_ke_file):
        background_tasks.add_task(os_sys.remove, path_ke_file)
        return FileResponse(path_ke_file, media_type="audio/mpeg")
    else:
        return {"error": "File kaga ketemu, Emi lagi puasa ngomong!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)