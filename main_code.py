from flask import Flask, request, jsonify, render_template_string
import json
import time
from collections import deque
import requests
import os

app = Flask(__name__)


GEMINI_API_KEY = "replace with your own GEMINI API KEY" #credit based for me 
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"


current_data = {
    "current_usage": 0.0,
    "energy_usage": 0.0,
    "power": 0.0,
    "advice": "Waiting for AI response..."
}
recent_readings = deque(maxlen=10)
total_energy = 0.0  # this is in kWh
last_update_time = time.time()  # track time difference precisely

# if gemini doesnt work, come back local
def local_advisor(power, current, energy):
    if power > 30:
        return " High load! Turn off non-essential devices."
    elif 10 < power <= 30:
        return " Moderate load — maintain efficiency."
    elif 3 < power <= 10:
        return " Low usage — optimal performance."
    elif power <= 3 and current < 0.05:
        return " Idle mode — minimal energy draw."
    else:
        return "⚡ Stable operation."

# advisor box
def ai_advisor(power, current, energy):
    prompt = f"""
    You are an AI Energy Assistant. 
    Analyze the readings and offer short, human-friendly smart insights
    along with next hour prediction to reduce bill by 15–30%.
    Power: {power:.2f} W, Current: {current:.2f} A, Energy: {energy:.3f} kWh.
    """

    try:
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(GEMINI_API_URL, json=payload, timeout=15)
        data = res.json()
        if "candidates" in data:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            print("- Gemini:", text)
            return "- " + text
    except Exception as e:
        print("Gemini error:", e)

    print(" Using local fallback.")
    return local_advisor(power, current, energy)


# our frontend
html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title> AI-Based Smart Energy Optimiser</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body {
    font-family: 'Poppins', sans-serif;
    background: radial-gradient(circle at top right, #0f172a, #020617);
    color: #e2e8f0;
    text-align: center;
    margin: 0;
    padding: 0;
  }
  h1 { font-size: 2.4rem; color: #38bdf8; margin-top: 30px; }
  .card-container {
    display: flex; justify-content: center; gap: 20px;
    flex-wrap: wrap; margin-top: 25px;
  }
  .card {
    background: linear-gradient(135deg, #1e293b, #334155);
    box-shadow: 0 0 20px rgba(56,189,248,0.2);
    border-radius: 15px; width: 260px; padding: 20px; transition: 0.3s;
  }
  .card:hover { transform: scale(1.05); box-shadow: 0 0 25px rgba(56,189,248,0.4); }
  .value { font-size: 2rem; color: #facc15; }
  #advisor { margin: 20px auto; padding: 15px; width: 85%;
    border-radius: 12px; font-weight: 500; text-align: center;
    background: linear-gradient(135deg,#0f766e,#115e59); color: #ecfccb;
    opacity: 0; transition: opacity 0.5s;
  }

  /* --- Floating Chatbot --- */
  #chatbot-toggle {
    position: fixed; bottom: 20px; right: 20px;
    background: #38bdf8; color: #0f172a; font-weight: bold;
    border: none; border-radius: 50%; width: 60px; height: 60px;
    box-shadow: 0 0 15px rgba(56,189,248,0.6);
    cursor: pointer; font-size: 1.5rem; transition: all 0.3s ease;
  }
  #chatbot-toggle:hover { transform: scale(1.1); background: #0ea5e9; }

  #chatbot-container {
    position: fixed; bottom: 90px; right: 20px;
    width: 320px; background: #1e293b; border-radius: 12px;
    box-shadow: 0 0 15px rgba(56,189,248,0.4);
    overflow: hidden; display: none; flex-direction: column;
  }
  #chatbot-header {
    background: #38bdf8; color: #0f172a; padding: 10px; font-weight: bold;
  }
  #chatbot-messages {
    flex: 1; padding: 10px; overflow-y: auto;
    font-size: 0.9rem; max-height: 250px;
  }
  .msg { margin: 6px 0; padding: 8px 12px; border-radius: 8px; max-width: 80%; }
  .user-msg { background: #38bdf8; color: #0f172a; align-self: flex-end; margin-left: auto; }
  .ai-msg { background: #334155; color: #f8fafc; align-self: flex-start; }
  #chatbot-input { display: flex; border-top: 1px solid #334155; }
  #chat-input { flex: 1; padding: 10px; border: none; background: #0f172a; color: #f8fafc; }
  #send-btn {
    background: #38bdf8; border: none; color: #0f172a; padding: 10px 15px;
    cursor: pointer; font-weight: bold;
  }
</style>
</head>
<body>
<h1> AI-Based Smart Energy Optimiser</h1>
<div class="card-container">
  <div class="card"><div>Current</div><div class="value" id="current">0.00 A</div></div>
  <div class="card"><div>Power</div><div class="value" id="power">0.00 W</div></div>
  <div class="card"><div>Energy</div><div class="value" id="energy">0.000 kWh</div></div>
</div>
<p id="status">Status: Waiting for data...</p>
<div id="advisor">AI Advisor: Initializing...</div>
<canvas id="energyChart" width="400" height="200"></canvas>

<!-- Chatbot UI -->
<button id="chatbot-toggle">💬</button>
<div id="chatbot-container">
  <div id="chatbot-header">Gemini 2.5 Flash Assistant ⚡</div>
  <div id="chatbot-messages"></div>
  <div id="chatbot-input">
    <input type="text" id="chat-input" placeholder="Ask me anything..." />
    <button id="send-btn">Send</button>
  </div>
</div>

<footer>Developed by Sai for live project </footer>

<script>
const ctx = document.getElementById('energyChart').getContext('2d');
const chart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: [],
    datasets: [
      { label: 'Power (W)', data: [], borderColor: '#facc15', fill: false, tension: 0.3 },
      { label: 'Current (A)', data: [], borderColor: '#38bdf8', fill: false, tension: 0.3 }
    ]
  },
  options: {
    scales: {
      x: { title: { display: true, text: 'Time' } },
      y: { beginAtZero: true, title: { display: true, text: 'Value' } }
    }
  }
});

function fadeIn(el, text) {
  el.style.opacity = 0;
  setTimeout(() => { el.innerText = text; el.style.opacity = 1; }, 200);
}

// Format energy neatly
function formatEnergy(value) {
  if (value < 0.001) return (value * 1000).toFixed(2) + " Wh";
  else if (value < 1) return value.toFixed(4) + " kWh";
  else return value.toFixed(2) + " kWh";
}

function updateUI(d) {
  document.getElementById('current').innerText = d.current_usage.toFixed(2) + " A";
  document.getElementById('power').innerText = d.power.toFixed(2) + " W";
  document.getElementById('energy').innerText = formatEnergy(d.energy_usage);
  fadeIn(document.getElementById('advisor'), "AI Advisor: " + d.advice);

  chart.data.labels.push(new Date().toLocaleTimeString());
  chart.data.datasets[0].data.push(d.power);
  chart.data.datasets[1].data.push(d.current_usage);

  if (chart.data.labels.length > 20) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
    chart.data.datasets[1].data.shift();
  }
  chart.update();
}

async function fetchData() {
  const r = await fetch('/latest');
  if (r.ok) updateUI(await r.json());
}
setInterval(fetchData, 2000);

// Chatbot functionality
const chatBox=document.getElementById("chatbot-messages");
const input=document.getElementById("chat-input");
document.getElementById("send-btn").addEventListener("click",sendMessage);
input.addEventListener("keypress",e=>{if(e.key==="Enter")sendMessage();});
async function sendMessage(){
 const text=input.value.trim(); if(!text)return;
 chatBox.innerHTML+=`<div class='msg user-msg'>${text}</div>`;
 input.value="";
 chatBox.scrollTop=chatBox.scrollHeight;
 const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:text})});
 const data=await res.json();
 chatBox.innerHTML+=`<div class='msg ai-msg'>${data.response}</div>`;
 chatBox.scrollTop=chatBox.scrollHeight;
}

// Toggle chatbot
const chatbotContainer=document.getElementById("chatbot-container");
const chatbotToggle=document.getElementById("chatbot-toggle");
let isOpen=false;
chatbotToggle.onclick=()=>{
  isOpen=!isOpen;
  chatbotContainer.style.display=isOpen?"flex":"none";
  chatbotToggle.innerText=isOpen?"✖️":"💬";
};
</script>
</body></html>
"""

@app.route('/')
def index():
    return render_template_string(html)

@app.route('/get_energy_data', methods=['POST'])
def get_energy_data():
    global current_data, total_energy, last_update_time
    try:
        data = request.get_json()
        if data:
            current = float(data.get("current_usage", 0))
            voltage = 9.0
            power = current * voltage

            #  convert Wh to kwh
            now = time.time()
            delta_t = now - last_update_time
            last_update_time = now
            total_energy += power * (2/3600.0) / 1000.0  * 100 #w.s conversion here

            advice = ai_advisor(power, current, total_energy)
            current_data = {
                "current_usage": current,
                "energy_usage": total_energy,
                "power": power,
                "advice": advice
            }
            print("Data received:", current_data)
            return jsonify({"status": "success"}), 200
    except Exception as e:
        print("Error:", e)
    return jsonify({"status": "failed"}), 400

@app.route('/latest')
def latest_data():
    return jsonify(current_data)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_input = data.get("query", "")
    prompt = f"You are an AI assistant helping a user manage energy efficiently.\nUser: {user_input}"
    try:
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(GEMINI_API_URL, json=payload, timeout=15)
        result = res.json()
        if "candidates" in result:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            return jsonify({"response": text})
        else:
            return jsonify({"response": " Gemini didn’t respond. Try again."})
    except Exception as e:
        print("Gemini Chat Error:", e)
        return jsonify({"response": " Error contacting Gemini."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True, threaded=True)
