
<p align="center">
  <img src="docs/banner.png" alt="Emi Health Assistant Banner" width="100%">
</p>

# Emi: An Edge-Based Self-Reflective RAG Health Assistant

[![Zenodo DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22038605.svg)](https://doi.org/10.5281/zenodo.22038605)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python: 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.60-red.svg)](https://streamlit.io/)

Implementation and supplemental codebase for the research paper:  
**"Dataset on System Performance, Usability, and User Acceptance of Emi: An Edge-Based Self-Reflective RAG Health Assistant"** (Submitted to *Data in Brief*, Elsevier)[cite: 1, 2, 7].

---

## 📌 Overview

**Emi** is an on-premise, privacy-preserving edge-AI conversational agent designed for Psychological First Aid (PFA) and Non-Communicable Disease (NCD) public health education in Semarang City[cite: 1, 7]. The system runs on consumer-grade hardware ($\le 8\text{ GB}$ VRAM) using 4-bit quantized Gemma 4[cite: 1, 7].

### Core Architecture & Capabilities
* **Edge Inference:** Local LLM reasoning via Ollama and Qdrant Vector Database on on-premise edge workstations[cite: 7, 9].
* **Document Ingestion:** Automated OCR parsing for tabular municipal PDF health profiles using GOT-OCR 2.0[cite: 7, 8].
* **Decoupled Fast-Path RAG:** Route-based prompt dispatching (Crisis PFA, Affective/Curhat, and Medical Guidelines) to minimize reasoning latency[cite: 7, 9].
* **Observability & Diagnostics:** Tracing of Time-To-First-Token (TTFT), token throughput, and RAGAS metrics via Arize Phoenix[cite: 7, 9].

---

## 📂 Repository Structure

```text
├── docs/
│   └── banner.png          # Cover banner image for repository documentation
├── emi_core2.py            # LangGraph orchestration, prompt templates, and retriever engine[cite: 9]
├── emi_api11.py            # FastAPI service: Streaming endpoints, deduplication, and Postgres logging[cite: 9]
├── app.py                  # Streamlit web interface with real-time TTS audio synthesis
├── mem_fill_GOT_2.ipynb    # Document ingestion pipeline (GOT-OCR 2.0 + Qdrant vector indexing)[cite: 8]
├── requirements.txt        # Production Python dependencies
├── .env.example            # Environment variable configuration template
├── .gitignore              # Ignored cache, model binaries, and runtime artifacts[cite: 10]
└── README.md               # Project documentation
```


---

## ⚙️ System Requirements

* **OS:** Linux (Ubuntu 22.04 LTS / WSL2)
* **GPU Hardware:** NVIDIA GTX 1070 Ti / P104-100 (8 GB VRAM)


* **Python Version:** $\ge 3.10$ (Tested on Python 3.12)
* **Underlying Services:**
* [Ollama](https://ollama.com/) (Serving `gemma4:latest` and `bge-m3:latest`)


* [Qdrant Vector Database](https://qdrant.tech/) (Port `6333`)


* [PostgreSQL](https://www.postgresql.org/) (Port `5432`)





---

## 🚀 Quickstart Guide

### 1. Repository Setup

```bash
git clone [https://github.com/](https://github.com/)Atanb-code/emi-health-assistant.git
cd emi-health-assistant

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

```

### 2. Environment Configuration

Copy `.env.example` to `.env` and set your local service credentials:

```bash
cp .env.example .env

```

Default parameters in `.env`:

```env
DB_NAME=emi_db
DB_USER=emi
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=5432
OLLAMA_BASE_URL=[http://127.0.0.1:11434](http://127.0.0.1:11434)
QDRANT_URL=[http://127.0.0.1:6333](http://127.0.0.1:6333)

```

### 3. Knowledge Base Ingestion

Place municipal health documents (such as *Profil Kesehatan Kota Semarang 2024*) inside `./data_awal/` and execute the indexing notebook:

```bash
jupyter notebook mem_fill_GOT_2.ipynb

```

Execute all cells to extract markdown tables via GOT-OCR 2.0 and index chunked embeddings into Qdrant.

### 4. Launch Backend API

Start the FastAPI server:

```bash
uvicorn emi_api11:app --host 0.0.0.0 --port 8000

```

* **API Service:** `http://127.0.0.1:8000`

* **Phoenix CCTV Tracing:** `http://127.0.0.1:6006`


### 5. Launch Frontend UI

In a separate terminal, start the Streamlit chat client:

```bash
streamlit run app.py

```

---

## 📊 Dataset & Artifacts

Empirical interaction logs ($N=115$) and user acceptance evaluation data ($N=20$) are available on Zenodo:

* **Zenodo DOI:** [10.5281/zenodo.22038605](https://www.google.com/url?sa=E&source=gmail&q=https://doi.org/10.5281/zenodo.22038605)

* **Archived Files:**
1. `1_Raw_Data_N20.csv` (TAM & SUS Survey Responses)
2. `2_Outer_Stage1_Comparison.csv` (Construct Reliability & Validity Metrics)
3. `3_Master_Outer_Loadings.csv` (Indicator Factor Loadings)
4. `4_Stage2_HOC_Weights_Loadings.csv` (Formative & Reflective HOC Parameters)
5. `5_Hypothesis_Bootstrapping.csv` (Structural Path Modeling & Mediation)
6. `6_DSR_Technical_Logs_N115.csv` (Latency, TTFT, and Accuracy Logs)
7. `7_BlackBox_Safety_Test.csv` (Boundary Verification Test Cases)



---

## 📖 Citation

```bibtex
@article{sinaga2026emi,
  title={Dataset on System Performance, Usability, and User Acceptance of Emi: An Edge-Based Self-Reflective RAG Health Assistant},
  author={Sinaga, Binsarniari and Ngatindriatun},
  journal={Data in Brief},
  year={2026},
  publisher={Elsevier},
  doi={10.5281/zenodo.22038605}
}

```

---

## 📜 License & Ethics

* **Source Code:** [MIT License](https://www.google.com/search?q=LICENSE)
* **Research Dataset:** [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
* **Ethical Compliance:** Survey data collection was conducted under explicit informed consent, anonymized in accordance with *Data in Brief* ethical guidelines.

