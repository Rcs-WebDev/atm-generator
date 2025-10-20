import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './App.css';

function App() {
  const [topic, setTopic] = useState('');
  const [idea, setIdea] = useState('');
  const [videos, setVideos] = useState([]); // <-- State baru untuk video
  const [isLoading, setIsLoading] = useState(false);
  const [isMakingVideo, setIsMakingVideo] = useState(false); // <-- State loading video
  const [error, setError] = useState('');

  const handleGenerate = async () => {
    // ... (fungsi ini tetap sama, tidak berubah)
    setVideos([]); // Reset video saat generate ide baru
    if (!topic) { setError('Topik tidak boleh kosong!'); return; }
    setIsLoading(true); setIdea(''); setError('');
    try {
      const response = await fetch('http://127.0.0.1:5001/api/generate-idea', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topic }),
      });
      const data = await response.json();
      if (response.ok) { setIdea(data.idea); } else { setError(data.error); }
    } catch (err) { setError('Gagal terhubung ke server.'); } finally { setIsLoading(false); }
  };

  // === FUNGSI BARU UNTUK MEMBUAT VIDEO ===
  const handleCreateVideo = async () => {
    setIsMakingVideo(true);
    setError('');
    try {
      const response = await fetch('http://127.0.0.1:5001/api/create-video', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: idea }), // Kirim teks ide ke backend
      });
      const data = await response.json();
      if (response.ok) {
        setVideos(data.videos);
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Gagal memproses permintaan video.');
    } finally {
      setIsMakingVideo(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚀 ATM Content Generator 🚀</h1>
        <div className="input-container">
          <input type="text" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Contoh: review smartphone terbaru" />
          <button onClick={handleGenerate} disabled={isLoading}>{isLoading ? 'Memproses...' : 'Hasilkan Ide'}</button>
        </div>

        {error && <p className="error-message">{error}</p>}

        {idea && (
          <div className="idea-result">
            <h3>✨ Ide Untuk Anda:</h3>
            <ReactMarkdown>{idea}</ReactMarkdown>
            {/* Tombol baru yang muncul setelah ide ada */}
            <button onClick={handleCreateVideo} disabled={isMakingVideo} className="video-button">
              {isMakingVideo ? 'Mencari Footage...' : '🎬 Buat Video Sederhana'}
            </button>
          </div>
        )}

        {/* Area baru untuk menampilkan hasil video */}
        {videos.length > 0 && (
          <div className="video-container">
            <h3>📹 Footage yang Ditemukan:</h3>
            <div className="video-grid">
              {videos.map((url, index) => (
                <video key={index} src={url} controls width="250" />
              ))}
            </div>
          </div>
        )}
      </header>
    </div>
  );
}

export default App;