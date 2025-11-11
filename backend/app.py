# app.py
import os
import re
import requests
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
from gtts import gTTS
from moviepy.editor import (
    VideoFileClip,
    concatenate_videoclips,
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
)
from moviepy.video.fx.all import resize
from PIL import Image

# Kompatibilitas Pillow versi baru
if not hasattr(Image, "ANTIALIAS"):
    from PIL import Image
    from PIL.Image import Resampling
    Image.ANTIALIAS = Resampling.LANCZOS

def clean_voiceover_text(raw_text: str) -> str:
    """Membersihkan teks agar hanya menyisakan narasi murni untuk voiceover & subtitle."""
    import re
    text = raw_text or ""

    # Hilangkan label instruksi di awal baris
    text = re.sub(
        r"(?mi)^\s*(VOICEOVER|Visual|Scene|Shot|Narasi|Audio|Text|Teks|Dialog|SFX)\s*[:：-]\s*",
        "",
        text,
    )

    # Hilangkan kalimat pembuka generatif ("Tentu, ini dia naskahnya..." dsb.)
    text = re.sub(
        r"(?i)\b(Tentu|Baiklah|Oke|Siap|Mari|Berikut|Nah|Jadi,|Sekarang)\b.*?(naskahnya|script|voiceover|di-record).*?[.!?]",
        "",
        text,
    )

    # Hilangkan tanda markdown atau simbol dekoratif
    text = re.sub(r"[\*\#\_`>]+", "", text)

    # Hilangkan tanda kurung atau bracket
    text = re.sub(r"\[.*?\]|\(.*?\)", "", text)

    # Hilangkan teks seperti "voice '...'"
    text = re.sub(r"(?i)\bvoice\b\s*['\"].*?['\"]", "", text)

    # Hilangkan sisa kata 'VOICEOVER' di tengah kalimat
    text = re.sub(r"(?i)\bVOICEOVER\b", "", text)

    # Rapikan spasi dan newline
    text = re.sub(r"\s+", " ", text).strip()

    # Pastikan hasil akhir tetap masuk akal
    if len(text.split()) < 3:
        text = "Narasi tidak terdeteksi."

    return text



# ============== INISIALISASI APP ==============
load_dotenv()
app = Flask(__name__)
CORS(app)

# ============== KONFIGURASI API KEY ==============
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-pro")
    print("✅ Model Gemini berhasil dikonfigurasi.")
except Exception as e:
    print(f"⚠️ Error konfigurasi Gemini: {e}")
    model = None


# ============== HELPER FUNCTIONS ==============
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


def generate_voiceover(text, voice_id="Rachel", lang="id"):
    tmp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    filepath = tmp_audio.name

    if ELEVEN_API_KEY:
        try:
            response = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": ELEVEN_API_KEY,
                },
                json={"text": text, "voice_settings": {"stability": 0.4, "similarity_boost": 0.8}},
            )
            if response.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(response.content)
                return filepath
            else:
                print("⚠️ ElevenLabs gagal, fallback ke gTTS.")
        except Exception as e:
            print("Error ElevenLabs:", e)

    # Fallback ke gTTS
    tts = gTTS(text, lang=lang)
    tts.save(filepath)
    return filepath


def download_pexels_videos(query, min_clips=3, max_clips=6):
    """Cari beberapa video relevan dari Pexels."""
    if not PEXELS_API_KEY:
        print("⚠️ PEXELS_API_KEY tidak ditemukan.")
        return []

    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": max_clips}
    response = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params)

    if response.status_code != 200:
        print("⚠️ Gagal mengambil video dari Pexels:", response.text)
        return []

    data = response.json()
    urls = []
    for video in data.get("videos", []):
        # Pilih video dengan resolusi medium ke atas
        file = next((f for f in video["video_files"] if f["width"] >= 720), None)
        if file:
            urls.append(file["link"])

    return urls[:max_clips]


def combine_video_audio(video_paths, audio_path, output_path):
    clips = [VideoFileClip(v).subclip(0, 5) for v in video_paths]
    final_clip = concatenate_videoclips(clips)
    audio = AudioFileClip(audio_path)
    final = final_clip.set_audio(audio)
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")
    return output_path


def combine_with_captions(video_paths, audio_path, script_text, output_path):
    """Gabungkan video + audio + subtitle otomatis"""
    from moviepy.editor import TextClip, CompositeVideoClip, concatenate_videoclips, VideoFileClip, AudioFileClip
    from moviepy.video.fx.all import resize
    import re

    cleaned_text = clean_voiceover_text(script_text)

    # Gabungkan semua klip video
    clips = []
    for path in video_paths:
        try:
            clip = resize(VideoFileClip(path).subclip(0, 5), width=720)
            clips.append(clip)
        except Exception as e:
            print(f"⚠️ Gagal proses clip {path}: {e}")

    if not clips:
        raise Exception("Tidak ada klip yang valid untuk digabungkan.")

    combined = concatenate_videoclips(clips, method="compose")

    audio = AudioFileClip(audio_path)
    combined = combined.set_audio(audio)

    # Subtitle otomatis per kalimat
    sentences = re.split(r"(?<=[.!?]) +", cleaned_text.strip())
    duration_per_sentence = audio.duration / max(len(sentences), 1)
    caption_clips = []

    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if not sentence:
            continue

        try:
            txt = TextClip(
                sentence,
                fontsize=40,
                color="white",
                bg_color="rgba(0,0,0,0.4)",
                size=(700, None),
                method="label",  # ⬅️ tidak butuh ImageMagick
                font="Arial-Bold",
            ).set_position(("center", "bottom")) \
             .set_start(i * duration_per_sentence) \
             .set_duration(duration_per_sentence)

            caption_clips.append(txt)
        except Exception as e:
            print(f"⚠️ Subtitle gagal untuk '{sentence[:30]}...': {e}")

    final = CompositeVideoClip([combined, *caption_clips]) if caption_clips else combined

    final.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=24)
    return output_path





# ============== ENDPOINT: VOICEOVER ==============@app.route("/api/voiceover", methods=["POST"])
def voiceover():
    try:
        data = request.get_json()
        raw_text = data.get("text", "")

        if not raw_text.strip():
            return jsonify({"error": "Teks untuk voiceover tidak boleh kosong."}), 400

        # ✨ Langkah 1: Bersihkan dan ubah teks agar natural untuk dibacakan
        prompt = f"""
        Ubah teks berikut agar cocok dibacakan dalam video pendek berdurasi 30–60 detik.
        Gunakan bahasa yang natural, storytelling ringan, dan mudah didengar.

        Teks sumber:
        {raw_text}
        """
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        improved_text_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Kamu adalah penulis naskah voiceover video pendek yang ahli dalam storytelling."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        improved_text = improved_text_response.choices[0].message.content.strip()

        # ✨ Langkah 2: Konversi hasil teks matang ke suara
        audio_path = os.path.join("output", f"voice_{uuid.uuid4().hex}.mp3")

        tts_response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=improved_text
        )
        tts_response.stream_to_file(audio_path)

        return send_file(audio_path, as_attachment=True, download_name="voiceover.mp3")

    except Exception as e:
        print(f"❌ Error voiceover: {e}")
        return jsonify({"error": str(e)}), 500



# ============== ENDPOINT: GENERATE SHORT ==============
@app.route("/api/generate-short", methods=["POST"])
def generate_short():
    """
    Buat video pendek otomatis berdasarkan teks (script).
    Durasi total video akan menyesuaikan panjang voiceover.
    """
    try:
        data = request.get_json()
        script_text = data.get("text", "")
        query = data.get("query", "")

        if not script_text:
            return jsonify({"error": "Teks narasi tidak ditemukan."}), 400

        print("🎙️ Membuat voiceover...")
        cleaned_text = clean_voiceover_text(script_text)
        voice_path = generate_voiceover(cleaned_text)
        voice_audio = AudioFileClip(voice_path)
        voice_duration = voice_audio.duration
        print(f"🔊 Durasi voiceover: {voice_duration:.2f} detik")

        # Gunakan kata-kata pertama dari teks sebagai keyword pencarian
        clean_text = re.sub(r"[\*\#\_]", "", script_text)
        keywords = query or " ".join(clean_text.split()[:5])
        print(f"🔍 Mencari footage untuk: {keywords}")

        video_urls = download_pexels_videos(keywords)
        if not video_urls:
            return jsonify({"error": "Tidak ada footage video yang ditemukan."}), 404

        # Unduh semua video dan simpan sementara
        video_files = []
        for url in video_urls:
            try:
                r = requests.get(url, timeout=30)
                tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tmp_file.write(r.content)
                tmp_file.close()
                video_files.append(tmp_file.name)
            except Exception as e:
                print(f"⚠️ Gagal unduh {url}: {e}")

        if not video_files:
            return jsonify({"error": "Semua download footage gagal."}), 500

        # Ambil potongan 5-10 detik dari tiap footage, lalu sambung sampai durasi cukup
        clips = []
        total_duration = 0
        target_duration = voice_duration

        for vpath in video_files:
            try:
                clip = VideoFileClip(vpath)
                dur = clip.duration
                sub_start = 0
                sub_end = min(10, dur)  # ambil maksimal 10 detik
                subclip = resize(clip.subclip(sub_start, sub_end), width=720)
                clips.append(subclip)
                total_duration += subclip.duration
                if total_duration >= target_duration:
                    break
            except Exception as e:
                print(f"⚠️ Gagal proses clip {vpath}: {e}")

        if not clips:
            return jsonify({"error": "Tidak ada video yang bisa digabungkan."}), 500

        print(f"🎞️ Total durasi footage: {total_duration:.2f} detik")

        combined = concatenate_videoclips(clips, method="compose")

        # Jika footage lebih panjang dari voiceover → potong
        if combined.duration > voice_duration:
            combined = combined.subclip(0, voice_duration)

        final = combined.set_audio(voice_audio)

        output_path = os.path.join(tempfile.gettempdir(), "video_short.mp4")
        final.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=24)

        print("✅ Video selesai dirender.")
        return send_file(output_path, mimetype="video/mp4", as_attachment=True, download_name="video_short.mp4")

    except Exception as e:
        print("❌ Error generate-short:", e)
        return jsonify({"error": str(e)}), 500


# ============== ENDPOINT BARU: RENDER VIDEO (DENGAN CAPTIONS) ==============
@app.route("/api/render-video", methods=["POST"])
def render_video():
    try:
        data = request.get_json()
        script_text = data.get("text", "")
        query = data.get("query", "motivational nature")

        if not script_text:
            return jsonify({"error": "Teks narasi tidak boleh kosong!"}), 400

        print("🎙️ Membuat voiceover...")
        cleaned_text = clean_voiceover_text(script_text)
        voice_path = generate_voiceover(cleaned_text)


        print("🎬 Mengunduh footage...")
        video_urls = download_pexels_videos(query)
        if not video_urls:
            return jsonify({"error": "Tidak ada video yang ditemukan di Pexels."}), 404

        video_files = []
        for idx, url in enumerate(video_urls):
            r = requests.get(url)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tmp.write(r.content)
            tmp.close()
            video_files.append(tmp.name)

        output_path = os.path.join(tempfile.gettempdir(), "final_render_with_captions.mp4")
        print("🧩 Menggabungkan video, audio, dan captions...")
        final_video = combine_with_captions(video_files, voice_path, script_text, output_path)

        return send_file(final_video, mimetype="video/mp4", as_attachment=True, download_name="video_final.mp4")

    except Exception as e:
        print("❌ Error render_video:", e)
        return jsonify({"error": str(e)}), 500


# ============== ENDPOINT: ANALYZE LINK (AMATI) ==============
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
        print(f"🎥 Mengambil transcript video ID: {video_id}")
        transcript_api = YouTubeTranscriptApi()
        transcript_list = transcript_api.fetch(video_id, languages=["id", "en"])
        transcript_text = " ".join([t.text for t in transcript_list])

        if not transcript_text:
            return jsonify({"error": "Tidak bisa mendapatkan transkrip dari video ini."}), 404

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
        print(f"❌ Error analyze_link: {e}")
        return jsonify({"error": str(e)}), 500


# ============== ENDPOINT: TIRU KONTEN ==============
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
        Analisis teks berikut dan ubah menjadi naskah konten video pendek yang menarik dan bernilai.
        Gaya penulisan: {style}.
        Transkrip:
        {source_text}

        Tulis hasil berbeda tergantung topik:
        - Jika topik podcast → ubah menjadi kalimat motivasi atau refleksi kehidupan yang kuat.
        - Jika topik barang/tempat → beri informasi tambahan yang belum dibahas, dan buat menarik secara visual.
        - Jika topik sejarah/kisah/biografi → tulis pelajaran hidup yang bisa memotivasi penonton.
        Output harus mengalir seperti narasi video pendek.
        """
        response = model.generate_content(prompt)
        result = response.text.strip()
        return jsonify({"result": result})
    except Exception as e:
        print(f"❌ Error tiru_content: {e}")
        return jsonify({"error": str(e)}), 500


# ============== ENDPOINT: GENERATE CAPTION ==============
@app.route("/api/generate-caption", methods=["POST"])
def generate_caption():
    data = request.get_json()
    topic = data.get("topic", "")
    language = data.get("lang", "id")

    if not topic:
        return jsonify({"error": "Topik video tidak boleh kosong."}), 400

    try:
        if not model:
            return jsonify({"error": "Model Gemini tidak tersedia."}), 500

        prompt = (
            f"Tuliskan caption pendek untuk video reels atau YouTube Shorts "
            f"dalam bahasa {language}, dengan gaya menarik dan mengandung emoji serta hashtag populer. "
            f"Topik video: {topic}"
        )

        result = model.generate_content(prompt)
        caption = result.text.strip()

        return jsonify({"caption": caption})
    except Exception as e:
        print("❌ Error generate-caption:", e)
        return jsonify({"error": str(e)}), 500


# ============== ENDPOINT: GENERATE IDEA ==============
@app.route("/api/generate-idea", methods=["POST"])
def generate_idea():
    try:
        data = request.get_json()
        topic = data.get("topic", "").strip()

        if not topic:
            return jsonify({"error": "Topik tidak boleh kosong."}), 400

        prompt = f"Buatkan ide konten menarik untuk topik: {topic}. Gunakan gaya bahasa yang ringan dan menarik penonton video short."
        response = model.generate_content(prompt)
        idea = response.text.strip() if hasattr(response, "text") else "Gagal menghasilkan ide."

        return jsonify({"idea": idea})
    except Exception as e:
        print("❌ Error generate_idea:", e)
        return jsonify({"error": str(e)}), 500


# ============== MAIN ==============
if __name__ == "__main__":
    app.run(debug=True, port=5001)
