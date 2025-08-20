import streamlit as st
import speech_recognition as sr
import requests
import json
import threading
import time
from datetime import datetime, timedelta
import queue
import tempfile
import os
import re
import random
import base64
import io
from gtts import gTTS
import pygame
import asyncio
import concurrent.futures

class StreamlitVoiceChatbot:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize pygame mixer for audio playback
        if 'audio_initialized' not in st.session_state:
            try:
                pygame.mixer.init()
                st.session_state.audio_initialized = True
            except Exception as e:
                st.error(f"Audio initialization error: {e}")
                st.session_state.audio_initialized = False
        
        # Ollama settings - fixed model
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "phi3:mini"
        
        # Initialize session state
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        if 'listening' not in st.session_state:
            st.session_state.listening = False
        if 'speaking' not in st.session_state:
            st.session_state.speaking = False
        if 'voice_enabled' not in st.session_state:
            st.session_state.voice_enabled = True
    
    def check_ollama_connection(self):
        """Check if Ollama is running"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def quick_response_check(self, message):
        """Check if we can answer quickly without AI"""
        msg_lower = message.lower().strip()
        
        # Simple math detection and calculation
        math_patterns = [
            r'(\d+(?:\.\d+)?)\s*[\+\-\*\/]\s*(\d+(?:\.\d+)?)',  # Direct: 2+2
            r'what\s+is\s+(\d+(?:\.\d+)?)\s*(plus|\+|minus|\-|times|\*|multiply|divided?\s*by|\/)\s*(\d+(?:\.\d+)?)',
            r'calculate\s+(\d+(?:\.\d+)?)\s*(plus|\+|minus|\-|times|\*|multiply|divided?\s*by|\/)\s*(\d+(?:\.\d+)?)'
        ]
        
        for pattern in math_patterns:
            match = re.search(pattern, message.lower())
            if match:
                try:
                    if len(match.groups()) == 2:  # Direct pattern like "2+2"
                        expr = match.group(0)
                        # Safe eval for basic math only
                        if re.match(r'^[\d\+\-\*\/\.\s\(\)]+$', expr):
                            result = eval(expr)
                            if isinstance(result, (int, float)):
                                if result == int(result):
                                    result = int(result)
                                return f"The answer is {result}"
                    else:  # Word pattern like "what is 5 plus 3"
                        num1 = float(match.group(1))
                        op = match.group(2).lower()
                        num2 = float(match.group(3))
                        
                        if op in ['plus', '+']:
                            result = num1 + num2
                        elif op in ['minus', '-']:
                            result = num1 - num2
                        elif op in ['times', '*', 'multiply']:
                            result = num1 * num2
                        elif op in ['divided by', 'divide by', '/']:
                            if num2 != 0:
                                result = num1 / num2
                            else:
                                return "I can't divide by zero!"
                        else:
                            continue
                        
                        # Format nicely
                        if result == int(result):
                            result = int(result)
                        return f"The answer is {result}"
                except:
                    continue
        
        # Quick date/time responses
        if any(phrase in msg_lower for phrase in ['what time', 'current time', 'time is']):
            current_time = datetime.now().strftime("%I:%M %p")
            return f"The current time is {current_time}"
        
        if 'tomorrow' in msg_lower and 'date' in msg_lower:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%A, %B %d, %Y")
            return f"Tomorrow will be {tomorrow}"
        
        if ('today' in msg_lower or 'current date' in msg_lower) and 'date' in msg_lower:
            today = datetime.now().strftime("%A, %B %d, %Y")
            return f"Today is {today}"
        
        if 'yesterday' in msg_lower and 'date' in msg_lower:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%A, %B %d, %Y")
            return f"Yesterday was {yesterday}"
        
        # Quick weather fallback
        if 'weather' in msg_lower:
            return "I don't have access to live weather data, but you can check your weather app or ask me something else!"
        
        return None  # No quick response available - use AI for natural conversation
    
    def chat_with_ollama(self, message):
        """Send message to Ollama and get response"""
        try:
            # Add current date context for date-related questions
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            current_time = datetime.now().strftime("%I:%M %p")
            
            system_prompt = f"""You are a friendly voice assistant. Today is {current_date} and the current time is {current_time}. 
            
            Your personality:
            - Conversational and natural
            - Supportive and understanding
            - Match the user's energy and tone
            - Keep responses under 100 words since this is voice chat
            - Don't greet repeatedly - you're in an ongoing conversation
            
            You can help with:
            - Natural conversation
            - General questions and advice
            - Creative tasks like stories and jokes
            
            Be authentic and helpful in your responses."""
            
            # Build conversation context from recent messages (last 6 messages for context)
            conversation_context = ""
            recent_messages = st.session_state.messages[-6:] if len(st.session_state.messages) > 6 else st.session_state.messages
            
            for msg in recent_messages:
                role = "User" if msg["role"] == "user" else "Assistant"
                # Clean content of emoji indicators
                clean_content = re.sub(r'\s*[⚡🤖]\s*', '', msg["content"]).strip()
                conversation_context += f"{role}: {clean_content}\n"

            # Compose the full message for the prompt
            full_message = f"{system_prompt}\n\nConversation so far:\n{conversation_context}\nAssistant:"

            payload = {
                "model": self.model,
                "prompt": full_message,
                "stream": False,
                "options": {
                    "temperature": 0.8,
                    "top_p": 0.9,
                    "max_tokens": 120,
                    "num_predict": 120,
                    "repeat_penalty": 1.1,
                    "top_k": 30
                },
                "keep_alive": "10m"
            }
            
            response = requests.post(self.ollama_url, json=payload, timeout=45)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = f" - {error_data.get('error', 'Unknown error')}"
                except:
                    error_detail = f" - Response: {response.text[:100]}"
                return f"Ollama Error {response.status_code}{error_detail}"
                
        except requests.exceptions.RequestException as e:
            return f"Sorry, I can't connect to Ollama right now. Make sure it's running! Error: {str(e)}"
        except Exception as e:
            return f"Something went wrong: {str(e)}"
    
    def play_audio_silently(self, text):
        """Convert text to speech and play without showing controls"""
        if not st.session_state.voice_enabled or not st.session_state.audio_initialized:
            return False
            
        try:
            # Clean text for better speech
            clean_text = re.sub(r'[⚡🤖]', '', text).strip()
            if not clean_text:
                return False
            
            # Create TTS
            tts = gTTS(text=clean_text, lang='en', slow=False)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                tts.save(tmp_file.name)
                tmp_file_path = tmp_file.name
            
            # Play audio in background thread to not block UI
            def play_audio():
                try:
                    pygame.mixer.music.load(tmp_file_path)
                    pygame.mixer.music.play()
                    
                    # Wait for playback to finish
                    while pygame.mixer.music.get_busy():
                        pygame.time.wait(100)
                    
                    # Clean up
                    try:
                        os.unlink(tmp_file_path)
                    except:
                        pass
                except Exception:
                    pass
            
            # Start audio in separate thread
            threading.Thread(target=play_audio, daemon=True).start()
            return True
            
        except Exception as e:
            st.error(f"Speech synthesis error: {e}")
            return False
    
    def listen_for_speech(self, timeout=10):
        """Listen for speech and convert to text"""
        try:
            with self.microphone as source:
                st.session_state.listening = True
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                # Listen for audio
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=15)
                st.session_state.listening = False
                
                # Convert speech to text
                text = self.recognizer.recognize_google(audio)
                return text
        except sr.UnknownValueError:
            return None
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            st.error(f"Speech recognition error: {e}")
            return None
        finally:
            st.session_state.listening = False
    
    def add_message(self, role, content):
        """Add message to chat history"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.messages.append({
            "role": role,
            "content": content,
            "timestamp": timestamp
        })

def main():
    st.set_page_config(
        page_title="Voice Assistant",
        page_icon="🎤",
        layout="centered"
    )
    
    # Initialize chatbot
    chatbot = StreamlitVoiceChatbot()
    
    # Header
    st.title("🎤 Voice Assistant")
    
    # Sidebar with controls
    with st.sidebar:
        st.header("Settings")
        
        # Voice settings
        st.session_state.voice_enabled = st.checkbox(
            "🔊 Enable Voice Output", 
            value=st.session_state.voice_enabled,
            help="Enable text-to-speech responses"
        )
        
        # Check Ollama connection
        ollama_connected = chatbot.check_ollama_connection()
        
        if ollama_connected:
            st.success("✅ Ollama Connected")
        else:
            st.error("❌ Ollama Disconnected")
            st.markdown("**Start Ollama:**")
            st.code("ollama serve", language="bash")
            st.markdown("**Install model:**")
            st.code("ollama pull phi3:mini", language="bash")
        
        st.divider()
        
        # Quick actions
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()
        
        st.divider()
        
        # Status
        st.subheader("Status")
        if st.session_state.get('listening', False):
            st.info("🎤 Listening...")
        else:
            st.success("✅ Ready")
        
        st.metric("Total Messages", len(st.session_state.messages))
        
        # Audio status
        if st.session_state.audio_initialized:
            st.success("🔊 Audio Ready")
        else:
            st.warning("🔇 Audio Unavailable")
    
    # Main interface - Voice input only
    st.subheader("Click to Talk")
    
    # Voice input button
    voice_button_disabled = st.session_state.get('listening', False) or not ollama_connected
    
    if st.button(
        "🎤 Start Voice Chat", 
        type="primary", 
        disabled=voice_button_disabled,
        help="Click and speak when prompted"
    ):
        with st.spinner("🎧 Listening... Speak now!"):
            user_input = chatbot.listen_for_speech(timeout=10)
        
        if user_input:
            # Add user message
            chatbot.add_message("user", user_input)
            
            # Try quick response first
            quick_response = chatbot.quick_response_check(user_input)
            if quick_response:
                # Play audio silently for quick response
                if st.session_state.voice_enabled:
                    chatbot.play_audio_silently(quick_response)
                
                # Instant response for simple stuff
                chatbot.add_message("assistant", quick_response + " ⚡")
            else:
                # Use AI for natural conversation
                with st.spinner("🤔 Thinking..."):
                    ai_response = chatbot.chat_with_ollama(user_input)
                
                # Play audio silently for AI response
                if st.session_state.voice_enabled:
                    chatbot.play_audio_silently(ai_response)
                
                # Add AI message
                chatbot.add_message("assistant", ai_response + " 🤖")
            
            st.rerun()
        else:
            st.warning("Couldn't hear you clearly. Try again!")
    
    # Display chat messages
    st.divider()
    st.header("Conversation:")
    
    if st.session_state.messages:
        for message in st.session_state.messages:
            timestamp = message["timestamp"]
            
            if message["role"] == "user":
                st.markdown(f"""
                <div style="background-color: #000; padding: 12px; border-radius: 15px; margin: 8px 0; border-left: 4px solid #2196f3;">
                    <strong>🧑 You</strong> <small style="color: #666;">({timestamp})</small><br>
                    <span style="font-size: 16px;">{message["content"]}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Check if it's a quick response or AI response
                is_quick = message["content"].endswith(" ⚡")
                bg_color = "#000" if is_quick else "#000"
                border_color = "#4caf50" if is_quick else "#e91e63"
                
                st.markdown(f"""
                <div style="background-color: {bg_color}; padding: 12px; border-radius: 15px; margin: 8px 0; border-left: 4px solid {border_color};">
                    <strong>🤖 Assistant</strong> <small style="color: #666;">({timestamp})</small><br>
                    <span style="font-size: 16px;">{message["content"]}</span>
                </div>
                """, unsafe_allow_html=True)
                    
    else:
        # Quick example buttons
        if not st.session_state.messages:
            st.subheader("Try Some Quick Examples")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("⚡ Math: 15×7") and ollama_connected:
                    chatbot.add_message("user", "What is 15 times 7?")
                    response = chatbot.quick_response_check("What is 15 times 7?")
                    if st.session_state.voice_enabled:
                        chatbot.play_audio_silently(response)
                    chatbot.add_message("assistant", response + " ⚡")
                    st.rerun()
            
            with col2:
                if st.button("⚡ Tomorrow's Date") and ollama_connected:
                    chatbot.add_message("user", "What's tomorrow's date?")
                    response = chatbot.quick_response_check("What's tomorrow's date?")
                    if st.session_state.voice_enabled:
                        chatbot.play_audio_silently(response)
                    chatbot.add_message("assistant", response + " ⚡")
                    st.rerun()
            
            with col3:
                if st.button("🤖 Tell Joke") and ollama_connected:
                    chatbot.add_message("user", "Tell me a funny joke!")
                    with st.spinner("Thinking..."):
                        response = chatbot.chat_with_ollama("Tell me a funny joke!")
                    if st.session_state.voice_enabled:
                        chatbot.play_audio_silently(response)
                    chatbot.add_message("assistant", response + " 🤖")
                    st.rerun()

if __name__ == "__main__":
    main()