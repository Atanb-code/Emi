
<p align="center">
  <img src="docs/emi-banner.png" alt="Emi Health Assistant Banner" width="100%">
</p>

# Emi: An Edge-Based Self-Reflective RAG Health Assistant

[![Zenodo DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22249913.svg)](https://doi.org/10.5281/zenodo.22249913)
[![License: Apache License ver 2](https://img.shields.io/badge/License-Apache_2-lightgray)](https://www.apache.org/licenses/LICENSE-2.0)
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
├── emi_core.py             # LangGraph orchestration, prompt templates, and retriever engine[cite: 9]
├── emi_api.py              # FastAPI service: Streaming endpoints, deduplication, and Postgres logging[cite: 9]
├── streamlit_emi.py        # Streamlit web interface with real-time TTS audio synthesis
├── mem_fill.ipynb          # Document ingestion pipeline (GOT-OCR 2.0 + Qdrant vector indexing)[cite: 8]
├── requirements.txt        # Production Python dependencies
├── .env.example            # Environment variable configuration template
├── .gitignore              # Ignored cache, model binaries, and runtime artifacts[cite: 10]
├── docker-compose.yml      # Docker container for Qdrant and PostgreSQL
└── README.md               # Project documentation
```


---

## ⚙️ System Requirements

* **OS:** Linux (Ubuntu 22.04 LTS / WSL2)
* **GPU Hardware:** Any NVIDIA Pascal or newer GPUs with minimum 8GB VRAM (In this case using GTX 1070Ti + P104-100 8GB)
* **Python Version:** $\ge 3.10$ (Tested on Python 3.12)

  **Underlying Services:**
* [Ollama](https://ollama.com/) (Serving `gemma4:12b-it-qat` and `bge-m3:latest`)
* [Qdrant Vector Database](https://qdrant.tech/) (Port `6333`)
* [PostgreSQL](https://www.postgresql.org/) (Port `5432`)
---

## 🚀 Quickstart Guide

### 1. Repository Setup
Before you clone everything, make sure if python3, pip, and venv is installed in your system. If not, you can do this following
```bash
# Update package list & install Python with its components

```

```bash
git clone https://github.com/Atanb-code/emi.git
cd emi

python3 -m venv venv          # You can name your own venv such as 'emi-venv' or anything else.
source [your-venv-name]/bin/activate
pip install --upgrade pip
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
OLLAMA_BASE_URL=http://127.0.0.1:11434
QDRANT_URL=http://127.0.0.1:6333

```

## 🐳 Container Infrastructure Setup (Docker)

Emi relies on Docker to orchestrate the Vector Database (Qdrant) and Relational Database (PostgreSQL) in an isolated edge environment[cite: 7].

### 1. Install Docker Engine

**Ubuntu / WSL2:**
```bash
# Install official Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Enable non-root Docker management
sudo usermod -aG docker $USER
newgrp docker

```

**Windows / macOS:**

* Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
* In Docker Desktop settings, verify that **Use the WSL 2 based engine** is active under **Settings** $\rightarrow$ **General** $\rightarrow$ **WSL Integration**.

---

### 2. Deploy Containers via Docker Compose

Launch the Qdrant vector engine and PostgreSQL database with a single command:

```bash
# Start containers in detached mode
docker compose up -d

# Verify container status
docker compose ps

```

| Service | Container Name | Host Ports | Purpose |
| --- | --- | --- | --- |
| **Qdrant** | `emi_qdrant` | `6333`, `6334` | Vector Database for RAG knowledge retrieval (`emi_knowledge`) |
| **PostgreSQL** | `emi_postgres` | `5432` | Relational logging of chats, ratings, and evaluation reports (`emi_db`) |

---

## 🌐 Edge-to-Cloud Funneling (Tailscale & Streamlit Cloud)

To deploy the Streamlit frontend publicly on **Streamlit Community Cloud** while keeping the inference backend, database, and models strictly local on your edge hardware, use **Tailscale Funnel** to establish a secure public HTTPS endpoint without port forwarding.

---

### 1. Configure Tailscale Funnel on Local Machine (WSL2 / Linux)

1. Install and authenticate [Tailscale](https://tailscale.com/):
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```

2. Enable **Funnel** in your [Tailscale Admin Console](https://tailscale.com/docs/features/tailscale-funnel) under **Access Controls** (grant `funnel` attribute for your node).

3. Expose the local FastAPI port via Tailscale Funnel in background mode:
```bash
tailscale funnel --bg 8000
```


4. Retrieve your public Tailscale HTTPS domain:
```bash
tailscale funnel status

```
*Expected output:* `https://node-name.your-tailnet.ts.net`

---

### 2. Deploy Frontend on Streamlit Community Cloud

1. Log in to [Streamlit Community Cloud](https://share.streamlit.io/) and click **New app**.
2. Select your repository, branch (`main`), and target file (`streamlit_emi.py`).
3. Under **Advanced settings** $\rightarrow$ **Secrets**, configure your public Tailscale backend URL:

```toml
# Streamlit Cloud Secrets (.streamlit/secrets.toml)
API_URL = "https://node-name.your-tailnet.ts.net/chat"
API_URL_STREAM = "https://node-name.your-tailnet.ts.net/chat_stream"
url_tts = "https://node-name.your-tailnet.ts.net/ngomong"
```

4. Click **Deploy**. The cloud-hosted frontend will now route prompts directly to your local edge-AI inference engine over encrypted TLS.


## 📚 Knowledge Base Ingestion & Vector "Rack" Construction

Follow these steps to initialize collections and ingest municipal health profiles or medical literature into Qdrant.

### 1. Document Preparation

Create the source directory and deposit all reference PDF files (e.g., *Profil Kesehatan Kota Semarang 2024*, PTM clinical guidelines, or empirical health journals):

```bash
mkdir -p data_awal
# Move all source PDF files into ./data_awal/

```

### 2. Local Model Pulling via Ollama

Ensure Ollama is running on the host machine and pull the required inference and embedding models:

```bash
ollama pull bge-m3:latest
ollama pull gemma4:12b-it-qat # or ollama pull gemma4:latest if your hardware is very limited, like using Pascal or older era GPUs

```

### 3. Build Vector Store & Run Memory Ingestion

Execute the ingestion pipeline to parse documents via GOT-OCR 2.0 and index embedding vectors into the Qdrant `emi_knowledge` collection:

```bash
jupyter notebook mem_fill.ipynb

```

* **OCR & Table Preservation:** Scanned pages are automatically detected and structured into Markdown tables using GOT-OCR 2.0.
* **Text Chunking:** Extracted texts are sliced into chunks ($1000$ characters with $200$ overlap).
* **Vector Injection:** Chunks are vectorized using `bge-m3` and injected into Qdrant.
* **State Checkpoint:** Ingestion progress is stored in `resume_log.json` to enable incremental updates.

### 4. Database Schema Initialization

The relational logging schema is initialized automatically upon starting the FastAPI backend, executing table creation for `chat_history`:

```bash
uvicorn emi_api:app --host 0.0.0.0 --port 8000

```


---

## 📊 Dataset & Artifacts

Empirical interaction logs ($N=115$) and user acceptance evaluation data ($N=20$) are available on Zenodo:

* **Zenodo DOI:** [10.5281/zenodo.22249913](https://doi.org/10.5281/zenodo.22249913)

* **Archived Files:**
1. `1_Raw_Data_N20.csv` (TAM & SUS Survey Responses)
2. `2_Outer_Stage1_Comparison.csv` (Construct Reliability & Validity Metrics)
3. `3_Master_Outer_Loadings.csv` (Indicator Factor Loadings)
4. `4_Stage2_HOC_Weights_Loadings.csv` (Formative & Reflective HOC Parameters)
5. `5_Hypothesis_Bootstrapping.csv` (Structural Path Modeling & Mediation)
6. `6_DSR_Technical_Logs_N115.csv` (Latency, TTFT, and Accuracy Logs)
7. `7_BlackBox_Safety_Test.csv` (Boundary Verification Test Cases)
8. `8_Survey_translated.docx` (Translated Post-Interaction Questionaire)



---

## 📖 Citation

```bibtex
@article{sinaga2026emi,
  title={Dataset on System Performance, Usability, and User Acceptance of Emi: An Edge-Based Self-Reflective RAG Health Assistant},
  author={Sinaga, Binsarniari and Ngatindriatun},
  journal={Data in Brief},
  year={2026},
  publisher={Elsevier},
  doi={10.5281/zenodo.22249913}
}

```

---

## 📜 License & Ethics

* **Source Code:** [License: Apache License ver 2](LICENSE)
* **Research Dataset:** [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
* **Ethical Compliance:** Survey data collection was conducted under explicit informed consent, anonymized in accordance with *Data in Brief* ethical guidelines.

