# backend/app.py
import os
import re
import requests # <-- Menggunakan library baru
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

# Ambil API keys dari .env
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Konfigurasi Google Gemini AI
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-pro')
    print("Model Gemini berhasil dikonfigurasi.")
except Exception as e:
    print(f"Error konfigurasi Gemini: {e}")
    model = None

@app.route('/api/generate-idea', methods=['POST'])
def generate_idea():
    # ... (Fungsi ini tidak berubah)
    if model is None: return jsonify({"error": "Model AI tidak terkonfigurasi."}), 500
    data = request.get_json()
    topic = data.get('topic')
    if not topic: return jsonify({"error": "Topik tidak boleh kosong!"}), 400
    try:
        prompt = f"""
        Anda adalah seorang pakar strategi konten YouTube. Berikan 3 ide video unik menggunakan metode ATM (Amati, Tiru, Modifikasi) untuk topik: "{topic}".
        Untuk setiap ide, berikan:
        1.  **Judul Video:** Judul yang menarik.
        2.  **Konsep Modifikasi (ATM):** Penjelasan singkat.
        3.  **Hook Pembuka:** Satu kalimat pembuka yang kuat.
        Gunakan format markdown.
        """
        response = model.generate_content(prompt)
        return jsonify({"idea": response.text})
    except Exception as e:
        print(f"Error saat memanggil API Gemini: {e}")
        return jsonify({"error": "Terjadi kesalahan saat menghasilkan ide dari AI."}), 500

# === FUNGSI CREATE_VIDEO YANG DITULIS ULANG TOTAL ===
@app.route('/api/create-video', methods=['POST'])
def create_video():
    if not PEXELS_API_KEY:
        return jsonify({"error": "Pexels API Key tidak ditemukan."}), 500

    data = request.get_json()
    text_idea = data.get('text', '')

    clean_text = re.sub(r'[\*\#\_]', '', text_idea)
    words = [word for word in clean_text.split() if len(word) > 4]
    keywords = words[:5]
    search_query = ' '.join(keywords)

    if not search_query:
        return jsonify({"error": "Tidak ada kata kunci yang bisa diekstrak."}), 400

    try:
        # 1. Siapkan URL dan Headers untuk Pexels API
        API_URL = "https://api.pexels.com/videos/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": search_query, "per_page": 5, "orientation": "landscape"}

        # 2. Kirim permintaan langsung ke Pexels
        response = requests.get(API_URL, headers=headers, params=params)
        response.raise_for_status()  # Ini akan otomatis error jika ada masalah (4xx or 5xx)
        
        pexel_data = response.json()
        videos = pexel_data.get('videos', [])

        if not videos:
            return jsonify({"error": f"Tidak ditemukan video untuk '{search_query}'."}), 404

        # 3. Proses hasilnya (logika ini tetap sama)
        video_urls = []
        for video in videos:
            hd_file = next((f for f in video['video_files'] if f['width'] == 1280 or f['height'] == 720), None)
            if hd_file:
                video_urls.append(hd_file['link'])
        
        if not video_urls:
             return jsonify({"error": f"Ditemukan video untuk '{search_query}', tapi tidak ada versi HD."}), 404
        
        return jsonify({"videos": video_urls})

    except requests.exceptions.RequestException as e:
        print(f"Error saat menghubungi Pexels: {e}")
        return jsonify({"error": "Gagal terhubung ke server Pexels."}), 500
    except Exception as e:
        print(f"Error tidak dikenal: {e}")
        return jsonify({"error": "Terjadi kesalahan internal."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)