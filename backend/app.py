# backend/app.py
import os
import re
import requests
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi  # <-- Library untuk transkrip YouTube

load_dotenv()
app = Flask(__name__)
CORS(app)

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ================== Konfigurasi Gemini ==================
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-pro")
    print("Model Gemini berhasil dikonfigurasi.")
except Exception as e:
    print(f"Error konfigurasi Gemini: {e}")
    model = None


# ================== FUNGSI BANTUAN ==================
def get_video_id(url):
    """Ekstrak video ID dari berbagai format link YouTube"""
    patterns = [
        r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})",
        r"(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})",
        r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


# ================== ENDPOINT: Generate Idea ==================
@app.route("/api/generate-idea", methods=["POST"])
def generate_idea():
    if model is None:
        return jsonify({"error": "Model AI tidak terkonfigurasi."}), 500
    data = request.get_json()
    topic = data.get("topic")
    if not topic:
        return jsonify({"error": "Topik tidak boleh kosong!"}), 400
    try:
        prompt = f"""
        Anda adalah pakar strategi konten YouTube. 
        Berikan saya 3 ide video unik (metode ATM) untuk topik: '{topic}'.
        Tampilkan:
        - Judul
        - Konsep ATM (Amati, Tiru, Modifikasi)
        - Hook pembuka
        Gunakan format markdown yang rapi.
        """
        response = model.generate_content(prompt)
        return jsonify({"idea": response.text})
    except Exception as e:
        print("Error generate-idea:", e)
        return jsonify({"error": "Gagal menghasilkan ide dari AI."}), 500


# ================== ENDPOINT: AMATI ==================
@app.route("/api/analyze-link", methods=["POST"])
def analyze_link():
    if model is None:
        return jsonify({"error": "Model AI tidak terkonfigurasi."}), 500

    data = request.get_json()
    video_url = data.get("url")

    video_id = get_video_id(video_url)
    if not video_id:
        return jsonify({"error": "Link YouTube tidak valid."}), 400

    try:
        # Ambil transkrip video
        transcript_api = YouTubeTranscriptApi()
        transcript_list = transcript_api.fetch(video_id, languages=["id", "en"])
        transcript_text = " ".join([t.text for t in transcript_list])

        if not transcript_text:
            return jsonify({"error": "Tidak bisa mendapatkan transkrip dari video ini."}), 404

        # Analisis isi video dengan Gemini
        prompt = f"""
        Anda adalah seorang analis video YouTube yang ahli.
        Berikut transkrip video:
        ---
        {transcript_text[:8000]}
        ---
        Lakukan analisis berikut:
        1. **Topik Utama**
        2. **Format Video**
        3. **Gaya Penyampaian**
        4. **Ringkasan Singkat (2 kalimat)**
        Sajikan hasil dalam format markdown.
        """
        response = model.generate_content(prompt)
        return jsonify({"analysis": response.text, "raw_transcript": transcript_text})

    except Exception as e:
        print(f"Error saat analisis link: {e}")
        return jsonify(
            {"error": "Gagal menganalisis video. Mungkin video ini tidak memiliki transkrip."}
        ), 500


# ================== ENDPOINT: TIRU ==================
@app.route("/api/tiru", methods=["POST"])
def tiru_content():
    if model is None:
        return jsonify({"error": "Model AI tidak terkonfigurasi."}), 500
    try:
        data = request.get_json()
        source_text = data.get("text", "")
        style = data.get("style", "gaya santai dan natural")

        if not source_text:
            return jsonify({"error": "Teks sumber tidak ditemukan."}), 400

        prompt = f"""
        Kamu adalah kreator konten profesional. 
        Buat ulang versi baru dari teks berikut tanpa menyalin kata-kata aslinya.
        Gunakan gaya {style}. 
        Teks sumber:
        {source_text}
        """
        response = model.generate_content(prompt)
        result = response.text.strip()
        return jsonify({"result": result})
    except Exception as e:
        print(f"Error saat tiru: {e}")
        return jsonify({"error": str(e)}), 500


# ================== ENDPOINT: MODIFIKASI ==================
@app.route("/api/modifikasi", methods=["POST"])
def modifikasi_content():
    if model is None:
        return jsonify({"error": "Model AI tidak terkonfigurasi."}), 500
    try:
        data = request.get_json()
        text = data.get("text", "")
        target_format = data.get("format", "caption Instagram inspiratif")

        if not text:
            return jsonify({"error": "Teks untuk dimodifikasi tidak ditemukan."}), 400

        prompt = f"""
        Ubah teks berikut menjadi format {target_format}.
        Pastikan hasilnya menarik, jelas, dan sesuai konteks.
        Gunakan bahasa alami yang mudah dipahami.
        ---
        {text}
        """
        response = model.generate_content(prompt)
        result = response.text.strip()
        return jsonify({"result": result})
    except Exception as e:
        print(f"Error saat modifikasi: {e}")
        return jsonify({"error": str(e)}), 500


# ================== ENDPOINT: CREATE VIDEO ==================
@app.route("/api/create-video", methods=["POST"])
def create_video():
    if not PEXELS_API_KEY:
        return jsonify({"error": "Pexels API Key tidak ditemukan."}), 500

    data = request.get_json()
    text_idea = data.get("text", "")
    clean_text = re.sub(r"[\*\#\_]", "", text_idea)
    words = [w for w in clean_text.split() if len(w) > 4]
    keywords = words[:5]
    search_query = " ".join(keywords)

    if not search_query:
        return jsonify({"error": "Tidak ada kata kunci."}), 400

    try:
        API_URL = "https://api.pexels.com/videos/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": search_query, "per_page": 5, "orientation": "landscape"}
        response = requests.get(API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        videos = data.get("videos", [])
        if not videos:
            return jsonify({"error": f"Tidak ditemukan video untuk '{search_query}'."}), 404

        video_urls = []
        for video in videos:
            hd_file = next(
                (f for f in video["video_files"] if f["width"] == 1280 or f["height"] == 720),
                None,
            )
            if hd_file:
                video_urls.append(hd_file["link"])

        if not video_urls:
            return jsonify({"error": "Tidak ada video HD."}), 404

        return jsonify({"videos": video_urls})
    except Exception as e:
        print("Error create-video:", e)
        return jsonify({"error": "Gagal terhubung ke Pexels."}), 500


# ================== MAIN ==================
if __name__ == "__main__":
    app.run(debug=True, port=5001)
