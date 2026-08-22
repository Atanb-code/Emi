from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

print("👷‍♂️ TUKANG BUILD QDRANT SIAP BEKERJA...")

# Konek ke server Qdrant lokal
client = QdrantClient(host="127.0.0.1", port=6333)

# DAFTAR RAK YANG MAU DI BIKIN (Bisa di tambahkan sesuai kebbutuhan)
# Misal: 1 buat Emi Dinkes, 1 buat bot yang lain
daftar_rak = ["emi_knowledge"]

for nama_rak in daftar_rak:
    # Cek dulu biar ga nabrak kalo raknya udah ada
    if not client.collection_exists(collection_name=nama_rak):
        print(f"🔨 Ngebangun rak baru: '{nama_rak}'...")
        client.create_collection(
            collection_name=nama_rak,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
        print(f"✅ Rak '{nama_rak}' sukses dibangun!")
    else:
        print(f"⚠️ Santai, rak '{nama_rak}' udah ada. Skip!")

print("🎉 SEMUA RAK SIAP DIISI JURNAL!")