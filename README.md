# Alfred — Personal AI Desktop Assistant for Windows 11

> *"At your service, Sir."*

Alfred is a classy, intelligent, professional butler-style desktop assistant for Windows 11 inspired by futuristic cinema. Operating as a native Windows desktop application, Alfred floats unobtrusively at the top center of your display (directly below the webcam), listening for wake phrases and responding with calm, concise spoken intelligence.

---

## Key Features

- **Single Floating Window**: Exactly one compact, frameless, translucent character window (160×160 px) placed at the top center of the screen. Clicking Alfred's image never opens a secondary chat window, dropdown panel, or popup.
- **Seven Animated Emotional States**: Fully powered by the 7 supplied character PNGs:
  - `v smoking.png`: Default idle state, waiting for wake commands.
  - `v cat.png`: Listening actively to user voice commands.
  - `v thinking.png`: Processing requests, querying news, and generating answers.
  - `v happy.png`: Positive results, task success, and friendly conversations.
  - `v sad.png`: Empathetic apologies, unavailable information, and errors.
  - `v cheers.png`: Celebrations, greetings, milestones, and achievements.
  - `v stop.png`: Immediate cancellation, speech stoppage, and paused states.
- **Fair Image Rotation**: Intelligently balances emotional character images using a rolling usage window in SQLite so all states are used fairly and regularly over time without flickering.
- **Voice-First Interaction**:
  - Wake phrases: **"Alfred"** and **"Hey Alfred"** (supports compound sentences such as *"Hey Alfred, what's happening in the markets?"*).
  - Stop phrases: **"Stop"**, **"Stop speaking"**, **"Cancel"**, **"Quiet, Alfred"** (instantly halts TTS playback and cancels active tasks).
- **Dual Voice Architecture**:
  - Primary: **ElevenLabs** for a natural, polished male butler voice.
  - Fallback: **Windows Native Speech** (SAPI5 / Microsoft David) when offline or without an API key.
- **Google Gemini Official SDK**: Powered by Google Gemini (`gemini-2.5-flash` / `gemini-2.0-flash`) for concise, grounded, dignified butler responses (1–3 sentences normally).
- **Daily Financial Briefing**:
  - Scheduled automatically at **8:30 AM Asia/Kolkata** (configurable).
  - Fetches real, verified financial news headlines (from RSS feeds, NewsAPI, AlphaVantage, or Finnhub).
  - Strictly grounded: Never fabricates stock prices, trades, or unverified claims.
  - Delivers via native Windows desktop notifications and optional spoken voice.
- **System Tray Integration**: Background tray menu to mute/unmute microphone, trigger manual briefings, clear history, or exit.
- **Secure Configuration**: All API keys reside strictly in `.env`. SQLite is used for local preferences and bounded conversation memory without storing secrets or raw audio.

---

## Project Structure

```text
Alfred/
├── main.py                     # Main application entry point
├── requirements.txt           # Project dependencies
├── .env.example               # Template environment configuration
├── .gitignore                 # Git ignore (excludes secrets and venv)
├── README.md                  # Comprehensive documentation
├── run_alfred.bat             # One-click Windows launch script
├── setup.bat                  # One-click Windows virtualenv and dependency setup
├── assets/                    # Seven character PNG assets
│   ├── v cat.png
│   ├── v cheers.png
│   ├── v happy.png
│   ├── v sad.png
│   ├── v smoking.png
│   ├── v stop.png
│   └── v thinking.png
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration dataclass & .env loader
│   ├── app.py                 # Core application orchestrator
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── floating_window.py # Single frameless top-center floating window
│   │   ├── image_manager.py   # Image loading, proportional scaling & caching
│   │   └── state_controller.py# State machine & fair image balancing
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── wake_word.py       # Local wake phrase & stop command detector
│   │   ├── speech_recognition.py # STT command capture
│   │   ├── text_to_speech.py  # ElevenLabs + Windows native TTS fallback
│   │   └── audio_manager.py   # Synchronizer & echo cancellation
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── gemini_client.py   # Google GenAI SDK wrapper
│   │   └── persona.py         # Butler personality, prompts, and cleaners
│   ├── services/
│   │   ├── __init__.py
│   │   ├── financial_news.py  # Real financial market news fetcher
│   │   ├── briefing.py        # APScheduler daily briefing manager
│   │   └── notifications.py   # Windows 11 action center notifications
│   ├── storage/
│   │   ├── __init__.py
│   │   └── database.py        # SQLite preferences, history, and usage stats
│   └── utils/
│       ├── __init__.py
│       └── logging_config.py  # Sensitive-data-safe rotating logger
├── data/                      # Local sqlite db and logs (auto-created)
└── tests/                     # Automated pytest suite (30 unit tests)
    ├── test_config.py
    ├── test_image_manager.py
    ├── test_state_controller.py
    ├── test_persona.py
    ├── test_briefing.py
    ├── test_database.py
    ├── test_ui_window.py
    └── test_voice.py
```

---

## Installation & Setup

### 1. Prerequisites
- **Windows 11** (or Windows 10 64-bit)
- **Python 3.11** or newer (with Python in your system PATH)
- Working microphone and speakers / headphones

### 2. Automated Setup (Recommended)
Double-click `setup.bat` or run:
```cmd
setup.bat
```
This script will:
1. Verify Python availability.
2. Create a virtual environment in `.venv/`.
3. Install all required dependencies from `requirements.txt`.
4. Copy `.env.example` to `.env` (preserving any existing `.env` file).
5. Prepare the `data/` directory.

### 3. Configure API Credentials
Open `.env` in any text editor (Notepad, VS Code):
```dotenv
# Google Gemini (https://aistudio.google.com/apikey)
GEMINI_API_KEY=your_actual_gemini_key
GEMINI_MODEL=gemini-2.5-flash

# ElevenLabs (https://elevenlabs.io/)
ELEVENLABS_API_KEY=your_actual_elevenlabs_key
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB
ELEVENLABS_MODEL_ID=eleven_multilingual_v2

# Financial News Provider (rss works out of the box with zero API keys required!)
FINANCIAL_NEWS_PROVIDER=rss
FINANCIAL_NEWS_API_KEY=
FINANCIAL_NEWS_BASE_URL=

# Daily briefing
ALFRED_DAILY_BRIEFING_ENABLED=true
ALFRED_DAILY_BRIEFING_TIME=08:30
ALFRED_TIMEZONE=Asia/Kolkata
```
> **Note:** If `ELEVENLABS_API_KEY` is omitted, Alfred automatically uses the built-in Windows native male speech (Microsoft David). If `GEMINI_API_KEY` is omitted, Alfred will launch normally and politely explain that his API key needs configuration.

### 4. Run Alfred
Double-click `run_alfred.bat` or run:
```cmd
run_alfred.bat
```

---

## Voice Commands Guide

| Trigger | Description |
|---|---|
| **"Alfred"** or **"Hey Alfred"** | Activates listening mode. The character transitions to `v cat.png` with a subtle chime. |
| **"Hey Alfred, what's happening in the markets?"** | Triggers the financial briefing service directly. |
| **"Alfred, explain quantum computing simply."** | Asks Gemini for a concise explanation. |
| **"Stop"** / **"Cancel"** / **"Quiet, Alfred"** | Immediately interrupts speech playback and switches to `v stop.png`. |
| **"Alfred, clear memory"** | Clears local SQLite conversation history. |

---

## Testing

Run the automated test suite with pytest:
```cmd
.venv\Scripts\python.exe -m pytest -v
```
All 30 unit tests cover:
- `.env` parsing, default fallbacks, and secret protection.
- Discovery and proportional scaling of all 7 character PNGs.
- State machine transitions (`IDLE → LISTENING → THINKING → SPEAKING → IDLE`).
- Fair image rotation balancing using SQLite usage history.
- Verification of single frameless window geometry and size invariants.
- Wake phrase and compound sentence matching.
- Stop command interruptions and instant TTS cancellation.
- Real financial RSS feed parsing and daily briefing generation.
- Database operations and bounded conversation retention.

---

## Troubleshooting

### Microphone not detecting wake phrase
- Open **Windows Settings → Privacy & Security → Microphone** and ensure microphone access is allowed for desktop apps.
- Adjust `ALFRED_SILENCE_TIMEOUT` in `.env` (default is `1.2` seconds).
- Right-click the Alfred system tray icon to verify microphone is not muted.

### Character window position
- By default, Alfred positions himself at the top center of your primary screen just below the webcam.
- You can freely drag the character window with your mouse.
- **Double-click** the character anytime to snap back to the exact top-center position.

### ElevenLabs quota exceeded or missing
- Alfred automatically detects missing or failed ElevenLabs requests and falls back to native Windows male speech (Microsoft David) with zero interruptions.

---

## License

Personal AI desktop assistant built for Windows 11.
