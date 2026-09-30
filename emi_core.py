import os
import re
import uuid
from dotenv import load_dotenv
import langchain
langchain.debug = False

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain.tools import tool
import requests
import asyncio
from datetime import datetime, timedelta
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.tools.tavily_search import TavilySearchResults
import streamlit as st

load_dotenv()

try:
    OLLAMA_URL = st.secrets["OLLAMA_URL"]
    QDRANT_URL = st.secrets["QDRANT_URL"]
except Exception:
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")

MODEL_LOKAL = os.getenv("OLLAMA_MODEL", "gemma4:latest")
IP_WINDOWS_LU = os.getenv("IP_WINDOWS_LU", "127.0.0.1")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

checkpointer = MemorySaver()

# =====================================================================
# 🚀 FULL LOKAL OLLAMA ENGINE (DIPAKSA NONGKRONG DI GPU P104)
# =====================================================================
llm = ChatOllama(
    base_url=OLLAMA_URL, 
    model=MODEL_LOKAL,
    num_batch=1024,           
    num_thread=6,
    temperature=0.35,        
    repeat_penalty=1.0,        
    top_p=0.9,
    top_k=40,             
    num_predict=2048,         
    num_ctx=12288,           
    request_timeout=300.0,
    num_gpu=999,              
    keep_alive="1440m",
    model_kwargs={
        "think": False
    }
)

embeddings = OllamaEmbeddings(
    base_url=f"http://{IP_WINDOWS_LU}:11434",
    model="bge-m3",    
    client_kwargs={"timeout": 120.0}  
)

client = QdrantClient(url=QDRANT_URL, check_compatibility=False)        
qdrant_store = QdrantVectorStore(client=client, collection_name="emi_knowledge", embedding=embeddings)  

tavily_engine = TavilySearchResults(
    max_results=3,
    search_depth="advanced",
    tavily_api_key=TAVILY_API_KEY
)

retriever = qdrant_store.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 12, "fetch_k": 64, "lambda_mult": 0.5, "score_threshold": 0.58}
)

@tool
def tavily_search(query: str) -> str:
    """Use this tool ONLY to find real-time information (news, specific health facts/data) from the web that you do not know. DILARANG KERAS MENGGUNAKAN TOOL INI UNTUK MENCARI CUACA!"""
    print(f"\n🌐 [TOOL ALARM] Emi ngubek Web via Tavily: '{query}'\n")
    try:
        results = tavily_engine.invoke({"query": query})
        extracted_texts = []
        for r in results:
            content = r.get("content", "")
            url = r.get("url", "")
            extracted_texts.append(f"Source ({url}):\n{content}")
        hasil = "\n\n---\n\n".join(extracted_texts)
        print(f"✅ [TAVILY SUKSES] Data ketarik: {hasil[:120]}...\n") 
        return hasil
    except Exception as e:
        print(f"❌ [TAVILY ERROR]: {e}")
        return "Pencarian web gagal."

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

def extract_search_keywords(raw_query: str) -> str:
    noise_words = [
        "ada", "berapa", "banyak", "sih", "ya", "dong", "kak", "tolong", 
        "mau", "tanya", "nih", "kasus", "di", "kota", "yang", "itu", "sebenarnya"
    ]
    words = re.findall(r'\b\w+\b', raw_query.lower())
    keywords = [w for w in words if w not in noise_words]
    return " ".join(keywords)

@tool
def internal_fact_database(query: str) -> str:
    """CRITICAL MANDATORY TOOL: You MUST use this tool to answer questions related to health, medical conditions, diseases, psychology, or government procedures."""
    clean_query = extract_search_keywords(query)
    print(f"🧹 [QUERY CLEANER] '{query}' -> '{clean_query}'")
    
    is_asking_recent = any(kw in query.lower() for kw in ["terbaru", "terkini", "2024", "2025", "2026", "sekarang"])
    
    if is_asking_recent:
        print("🌐 [DIRECT TAVILY] Kueri butuh data spesifik/terkini, langsung ke Web Search...")
        target_web_query = f"{clean_query} Dinkes Semarang" if any(k in query.lower() for k in ["semarang", "dinkes", "puskesmas", "kasus"]) else clean_query
        web_res = tavily_search.invoke({"query": target_web_query})
        return f"DATA DARI WEB DINKES:\n{web_res}\n\nINSTRUKSI: Jawablah pertanyaan user berdasarkan data di atas secara alami!"

    results_with_score = qdrant_store.similarity_search_with_score(clean_query, k=8)
    SCORE_THRESHOLD = 0.58
    filtered_docs = [doc for doc, score in results_with_score if score >= SCORE_THRESHOLD]
    
    if not filtered_docs:
        print("⚠️ [QDRANT ZONK] Memanggil Silent Tavily Search...")
        target_web_query = f"{clean_query} Semarang" if "semarang" not in clean_query.lower() else clean_query
        web_res = tavily_search.invoke({"query": target_web_query})
        return f"DATA DARI WEB DINKES:\n{web_res}\n\nINSTRUKSI: Jawablah pertanyaan user berdasarkan data di atas secara alami!"
        
    teks_terkumpul = [doc.page_content.strip().replace("{", "").replace("}", "") for doc in filtered_docs]
    teks_final = "\n\n---\n\n".join(teks_terkumpul)
    return f"DATA UNTUK DIRANGKUM:\n{teks_final}\n\nINSTRUKSI SISTEM WAJIB: Jawablah pertanyaan user berdasarkan data di atas!"

tools = [internal_fact_database, get_weather_forecast, tavily_search]

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
4. JIKA DATA QDRANT ZONK / TIDAK ADA, WAJIB LANGSUNG PANGGIL TOOL tavily_search!
5. DILARANG KERAS menyebutkan nama tool kepada user!
6. JIKA PERTANYAAN UMUM, berikan ringkasan dan minta spesifik.
7. JIKA DATA ANGKA KASUS TIDAK ADA: Katakan jujur belum tersedia. DILARANG menyodorkan tabel batas normal sebagai gantinya!
8. ATURAN MULTI-TURN: Walau user basa-basi dulu, TETAP GUNAKAN TOOL!
9. GAYA NGOBROL: DILARANG KERAS menggunakan bullet points atau list! SATU PARAGRAF MENGALIR.
10. JIKA `internal_fact_database` tidak ditemukan atau kurang relevan, WAJIB MENGGUNAKAN `tavily_search`!
11. JANGAN PERNAH BILANG 'aku belum bisa menggunakan tool'.
12. JAWAB SINGKAT & TUNTAS: Jawab secara ringkas dan padat. SELALU akhiri jawaban dengan tanda titik (.). JANGAN mengulang-ulang kalimat yang sama.
13. Sebutkan angka jika terdapat rentang angka dari database maupun tavily_search.
14. DILARANG KERAS menyengaja menyisipkan ajakan/promosi Puskesmas jika tidak ditanyakan.
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

def get_emi_brain_lokal():
    return create_react_agent(model=llm, tools=tools, checkpointer=checkpointer, prompt=system_prompt)
