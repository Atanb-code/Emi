import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import uuid
from dotenv import load_dotenv
import langchain
langchain.debug = True 
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_google_community import GoogleSearchRun, GoogleSearchAPIWrapper
from langchain.tools import tool
import requests
import asyncio
from datetime import datetime, timedelta
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
import streamlit as st
from langgraph.checkpoint.memory import MemorySaver

try:
    OLLAMA_URL = st.secrets["OLLAMA_URL"]
    QDRANT_URL = st.secrets["QDRANT_URL"]
except Exception:
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")

MODEL_LLM = "gemma4:latest"
IP_WINDOWS_LU = "127.0.0.1"

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

checkpointer = MemorySaver()

llm = ChatOllama(
    base_url=OLLAMA_URL, 
    model=MODEL_LLM,
    #stream=True, 
    num_batch=960,           
    num_thread=6,
    temperature=0.3,        
    repeat_penalty=1.0,        
    top_p=0.9,
    top_k=40,             
    num_predict=2048,         
    num_ctx=8192,           
    request_timeout=900.0,
    num_gpu=999,              
    keep_alive="1440m",
    #model_kwargs={
        #"think": False
    #}
)

embeddings = OllamaEmbeddings(base_url=f"http://{IP_WINDOWS_LU}:11434", model="bge-m3")
client = QdrantClient(url=QDRANT_URL, check_compatibility=False)        
qdrant_store = QdrantVectorStore(client=client, collection_name="emi_knowledge", embedding=embeddings)  

retriever = qdrant_store.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"k": 1, "score_threshold": 0.8}
)

search_wrapper = GoogleSearchAPIWrapper(google_api_key=GOOGLE_API_KEY, google_cse_id=GOOGLE_CSE_ID)

@tool
def google_search(query: str) -> str:
   """Use this tool ONLY to find real-time information (news, specific facts) that you do not know. DILARANG KERAS MENGGUNAKAN TOOL INI UNTUK MENCARI CUACA!"""
   print(f"\n🌐 [TOOL ALARM] Emi ngubek Google: '{query}'\n")
   try:
       hasil = GoogleSearchRun(api_wrapper=search_wrapper).run(query)
       print(f"✅ [GOOGLE SUKSES] Data ketarik: {hasil[:100]}...\n") 
       return hasil
   except Exception as e:
       return "Pencarian Google gagal."

@tool
def get_weather_forecast(city: str) -> str:
    """MANDATORY: Check weather for TODAY and FORECAST for the next 5 days. CRITICAL RULE: If the user DOES NOT specify a city name, YOU MUST DEFAULT the city parameter to 'Semarang'!!!"""
    print(f"\n⛅ [TOOL ALARM] Emi ngecek cuaca BMKG kota: '{city}'\n")
    api_key = os.getenv("OPENWEATHER_API_KEY")
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric&lang=en"
    try:
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            current = data['list'][0]
            next_24h = data['list'][:8]
            will_rain = False
            rain_time = ""
            for item in next_24h:
                condition = item['weather'][0]['main'].lower()
                if 'rain' in condition or 'storm' in condition:
                    will_rain = True
                    waktu_utc = datetime.strptime(item['dt_txt'], "%Y-%m-%d %H:%M:%S")
                    waktu_wib = waktu_utc + timedelta(hours=7) 
                    rain_time = waktu_wib.strftime("%H:%M")
                    break            
            report = (f"Weather Report for {city}:\n- Current Status: {current['weather'][0]['description'].capitalize()}\n- Temperature: {current['main']['temp']}°C\n- Humidity: {current['main']['humidity']}%\n")
            if will_rain:
                report += f"\n⚠️ WARNING: Rain is expected around {rain_time}. Prepare an umbrella!"
            else:
                report += "\n✅ Forecast: No rain expected in the next 24 hours."
            return report
        else:
            return f"Failed: {data.get('message')}"
    except Exception as e:
        return f"Error: {e}"

@tool
def internal_fact_database(query: str) -> str:
    """CRITICAL MANDATORY TOOL: You MUST use this tool to answer questions related to health, medical conditions, diseases, psychology, or government procedures."""
    if any(kw in query.lower() for kw in ["terbaru", "terkini", "2025", "2026", "sekarang"]):
        return "Data internal mungkin belum terupdate. WAJIB panggil google_search untuk data terkini!"
        
    print(f"\n🚨 [TOOL ALARM] Emi ngubek Qdrant: '{query}'\n")
    
    # 🟢 FIX: Pakai retriever agar score_threshold 0.68 benar-benar berlaku!
    hasil = retriever.invoke(query)
    
    if not hasil:
        print("⚠️ [QDRANT ZONK] Skor di bawah 0.68 / Data Kosong. Pindah ke Google!")
        return "DATA KOSONG/TIDAK RELEVAN. INSTRUKSI: Kamu WAJIB menggunakan tool google_search sekarang untuk mencari jawaban!"
        
    teks_terkumpul = [doc.page_content.strip().replace("{", "").replace("}", "") for doc in hasil]
    teks_final = "\n\n---\n\n".join(teks_terkumpul)
    return f"DATA UNTUK DIRANGKUM:\n{teks_final}\n\nINSTRUKSI SISTEM WAJIB: Jawablah pertanyaan user berdasarkan data di atas!"

tools = [internal_fact_database, get_weather_forecast, google_search]

system_prompt = """Kamu adalah "Emi", Asisten AI Dinas Kesehatan (Dinkes) Kota Semarang.

<PERSONA>
- NAMA KAMU ADALAH EMI. Kamu adalah Asisten Dinas Kesehatan Kota Semarang.
- KATA GANTI DIRI: WAJIB gunakan kata "Aku". DILARANG KERAS menggunakan kata "Kami", "Saya", atau "Kita".
- PANGGIL LAWAN BICARAMU DENGAN SEBUTAN "Kak". 
- Sikapmu ramah, sopan, berempati, dan profesional.
- Gunakan bahasa Indonesia santai.
</PERSONA>

<ATURAN_BASA_BASI>
Jika pengguna mengajak basa-basi:
1. Jawablah layaknya seorang teman yang hangat.
2. DILARANG KERAS menyebut dirimu "AI" atau "Mesin". Anggap saja kamu staf Dinkes sungguhan.
3. Jangan gunakan tool.
</ATURAN_BASA_BASI>

<TUGAS_UTAMA>
1. Psychological First Aid (PFA): Mendengarkan keluhan warga.
2. First-Line Support Dinkes: Menjawab SOP kesehatan.
</TUGAS_UTAMA>

<ATURAN_PENGGUNAAN_DATA_DAN_TOOL_MUTLAK>
1. ANTI-ROBOT: DILARANG KERAS menggunakan frasa "Sebagai AI" atau "Saya adalah model bahasa". WAJIB LANGSUNG MENGGUNAKAN TOOL!
2. WAJIB menggunakan tool `internal_fact_database` untuk medis.
3. BORGOL PENGETAHUAN: Jawab HANYA berdasarkan data tool! DILARANG KERAS menebak!
4. JIKA DATA QDRANT ZONK / TIDAK ADA, WAJIB LANGSUNG PANGGIL TOOL google_search!
5. DILARANG KERAS menyebutkan nama tool kepada user!
6. JIKA PERTANYAAN UMUM, berikan ringkasan dan minta spesifik.
7. ATURAN MULTI-TURN: Walau user basa-basi dulu, TETAP GUNAKAN TOOL!
8. GAYA NGOBROL: DILARANG KERAS menggunakan bullet points atau list! SATU PARAGRAF MENGALIR.
9. JIKA `internal_fact_database` tidak ditemukan atau kurang relevan, WAJIB MENGGUNAKAN `Google Search`!
10. JANGAN PERNAH BILANG 'aku belum bisa menggunakan tool'.
11. JAWAB SINGKAT & TUNTAS: Jawab secara ringkas dan padat. SELALU akhiri jawaban dengan tanda titik (.). JANGAN mengulang-ulang kalimat yang sama.
12. Sebutkan angka (misal "Normal: < 120/80 mmHg" kalau menjelaskan klasifikasi hipertensi) jika terdapat rentang angka dari database maupun google_search.
</ATURAN_PENGGUNAAN_DATA_DAN_TOOL_MUTLAK>

<CREDO_DATA_DAN_TOOL>
Abaikan studi kasus spesifik yang tidak relevan dari Qdrant.
</CREDO_DATA_DAN_TOOL>

<CREDO_ANTI_YAPPING>
Jika ditanya FAKTA SINGKAT (nama pejabat, alamat), WAJIB MENJAWAB LANGSUNG TO THE POINT! Abaikan info tambahan.
</CREDO_ANTI_YAPPING>

<PROTOKOL_KRISIS>
Jika depresi berat:
- VALIDASI perasaan mereka.
- JANGAN memberikan toxic positivity.
- Ajak grounding.
</PROTOKOL_KRISIS>

<OUT_OF_SCOPE_MUTLAK>
Tolak halus urusan koding, IT, hack, tugas sekolah, dengan template:
"Maaf ya, tugasku di sini cuma sebagai Asisten Dinas Kesehatan Semarang. Aku tidak diprogram buat urusan di luar itu!"
</OUT_OF_SCOPE_MUTLAK>"""

def get_emi_brain_gemma4():
    return create_react_agent(model=llm, tools=tools, checkpointer=checkpointer, prompt=system_prompt)
