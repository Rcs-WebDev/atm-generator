import { useState } from "react";
import ReactMarkdown from "react-markdown";
import "./App.css";

function App() {
  const [topic, setTopic] = useState("");
  const [idea, setIdea] = useState("");
  const [analysis, setAnalysis] = useState("");
  const [modifiedIdea, setModifiedIdea] = useState("");
  const [videos, setVideos] = useState([]);
  const [caption, setCaption] = useState("");
  const [voiceUrl, setVoiceUrl] = useState("");
  const [finalVideoUrl, setFinalVideoUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isModifying, setIsModifying] = useState(false);
  const [isMakingVideo, setIsMakingVideo] = useState(false);
  const [error, setError] = useState("");

  const isYoutubeLink = (url) => {
    const p =
      /^(?:https?:\/\/)?(?:www\.)?(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))((\w|-){11})(?:\S+)?$/;
    return url.match(p) ? true : false;
  };

  const handleGenerate = async () => {
    if (!topic) {
      setError("Input tidak boleh kosong!");
      return;
    }

    setIsLoading(true);
    setIdea("");
    setAnalysis("");
    setModifiedIdea("");
    setVideos([]);
    setError("");

    try {
      let response;
      if (isYoutubeLink(topic)) {
        response = await fetch("http://127.0.0.1:5001/api/analyze-link", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: topic }),
        });
        const data = await response.json();
        if (response.ok) {
          setAnalysis(data.analysis);
        } else {
          setError(data.error);
        }
      } else {
        response = await fetch("http://127.0.0.1:5001/api/generate-idea", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ topic: topic }),
        });
        const data = await response.json();
        if (response.ok) {
          setIdea(data.idea);
        } else {
          setError(data.error);
        }
      }
    } catch (err) {
      setError("Gagal terhubung ke server.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleTiru = async () => {
    if (!analysis) return;
    setIsModifying(true);
    setError("");
    try {
      const response = await fetch("http://127.0.0.1:5001/api/tiru", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: analysis, style: "gaya santai dan natural" }),
      });
      const data = await response.json();
      if (response.ok) {
        setModifiedIdea(data.result);
      } else {
        setError(data.error);
      }
    } catch {
      setError("Gagal meniru konten.");
    } finally {
      setIsModifying(false);
    }
  };

  const handleModifikasi = async () => {
    const textToModify = modifiedIdea || idea;
    if (!textToModify) return;
    setIsModifying(true);
    setError("");
    try {
      const response = await fetch("http://127.0.0.1:5001/api/modifikasi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textToModify }),
      });
      const data = await response.json();
      if (response.ok) {
        setModifiedIdea(data.result);
      } else {
        setError(data.error);
      }
    } catch {
      setError("Gagal memodifikasi ide.");
    } finally {
      setIsModifying(false);
    }
  };

  const handleVoiceover = async () => {
    const textToUse = modifiedIdea || idea || analysis;
    if (!textToUse) return;
    setError("");
    try {
      const response = await fetch("http://127.0.0.1:5001/api/voiceover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textToUse }),
      });
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setVoiceUrl(url);
      } else {
        const data = await response.json();
        setError(data.error);
      }
    } catch {
      setError("Gagal membuat voiceover.");
    }
  };

  const handleCreateVideo = async () => {
    setIsMakingVideo(true);
    setError("");
    const textToUse = modifiedIdea || idea || analysis;
    try {
      const response = await fetch("http://127.0.0.1:5001/api/generate-short", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textToUse }),
      });
      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setFinalVideoUrl(url);
      } else {
        const data = await response.json();
        setError(data.error);
      }
    } catch {
      setError("Gagal membuat video short.");
    } finally {
      setIsMakingVideo(false);
    }
  };

  const handleGenerateCaption = async () => {
    const textToUse = modifiedIdea || idea || analysis;
    if (!textToUse) return;
    setError("");
    try {
      const response = await fetch("http://127.0.0.1:5001/api/generate-caption", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: textToUse }),
      });
      const data = await response.json();
      if (response.ok) {
        setCaption(data.caption);
      } else {
        setError(data.error);
      }
    } catch {
      setError("Gagal membuat caption otomatis.");
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚀 ATM Content Generator 🚀</h1>
        <p>
          Masukkan <b>topik</b> atau <b>link YouTube</b> untuk memulai proses ATM
          (Amati, Tiru, Modifikasi).
        </p>

        <div className="input-container">
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Contoh: resep nasi goreng atau link YouTube"
          />
          <button onClick={handleGenerate} disabled={isLoading}>
            {isLoading ? "Memproses..." : "Amati / Hasilkan Ide"}
          </button>
        </div>

        {error && <p className="error-message">{error}</p>}

        {analysis && (
          <div className="idea-result">
            <h3>✨ Hasil Analisis Video (Amati):</h3>
            <ReactMarkdown>{analysis}</ReactMarkdown>
            <button onClick={handleTiru} disabled={isModifying}>
              {isModifying ? "Meniru..." : "🤖 Tiru Konten Ini"}
            </button>
          </div>
        )}

        {(idea || modifiedIdea) && (
          <div className="idea-result">
            <h3>✨ Ide Kreatif Anda (Tiru / Modifikasi):</h3>
            <ReactMarkdown>{modifiedIdea || idea}</ReactMarkdown>
            <div className="button-group">
              <button onClick={handleModifikasi} disabled={isModifying}>
                {isModifying ? "Memodifikasi..." : "🧠 Modifikasi Lagi"}
              </button>
              <button onClick={handleVoiceover}>🎧 Voiceover</button>
              <button onClick={handleCreateVideo} disabled={isMakingVideo}>
                {isMakingVideo ? "Menggabungkan..." : "🎬 Buat Video Short"}
              </button>
              <button onClick={handleGenerateCaption}>💬 Caption Otomatis</button>
            </div>

            {voiceUrl && (
              <div>
                <h4>🎤 Voiceover Preview:</h4>
                <audio controls src={voiceUrl}></audio>
              </div>
            )}

            {caption && (
              <div>
                <h4>💬 Caption Otomatis:</h4>
                <p>{caption}</p>
              </div>
            )}

            {finalVideoUrl && (
              <div>
                <h4>📽️ Video Short Siap Posting:</h4>
                <video controls src={finalVideoUrl} width="300"></video>
                <br />
                <a href={finalVideoUrl} download="video_short.mp4">
                  ⬇️ Download Video
                </a>
              </div>
            )}
          </div>
        )}
      </header>
    </div>
  );
}

export default App;
