requirements.txt (you can drop straight into your project):

speechrecognition==3.10.0
pyttsx3==2.90
pyaudio==0.2.14
ollama==0.1.6

⚡ Notes on why these are needed:

speechrecognition → handles converting your voice to text.

pyttsx3 → text-to-speech engine for responses.

pyaudio → required backend for microphone input (speechrecognition depends on it).

ollama → Python client to interact with the Ollama LLM running locally.

🔧 Installation:
pip install -r requirements.txt


⚠️ One catch: PyAudio can sometimes be tricky to install on Windows. If you hit issues, you may need to download the .whl file from PyAudio wheels
 and install with:
 
pip install PyAudio-0.2.14-cp310-cp310-win_amd64.whl

🚀 How to Run

Clone the repository:

git clone https://github.com/your-username/voice-assistant.git
cd voice-assistant


Start Ollama locally:

ollama run llama2


Run the script:

python voice_task_manager.py
