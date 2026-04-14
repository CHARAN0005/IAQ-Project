from flask import Flask, request, jsonify
import pandas as pd
import joblib
import os
import subprocess
import logging

# ---------------- CLEAN LOGS ----------------
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)

# ---------------- GLOBAL STORAGE ----------------
last_data = {"aqi": 0, "fan": 0, "fogger": 0}

# ---------------- PATHS ----------------
MODEL_PATH = "air_quality_model.pkl"
DATA_PATH = "dataset.csv"

model = None

# ---------------- AUTO TRAIN FUNCTION ----------------
def train_if_needed():
    try:
        if not os.path.exists(MODEL_PATH):
            print(" Model not found. Training now...")
            subprocess.run(["python", "train_model.py"])
            print(" Training completed!")

        elif os.path.exists(DATA_PATH):
            model_time = os.path.getmtime(MODEL_PATH)
            data_time = os.path.getmtime(DATA_PATH)

            if data_time > model_time:
                print(" Dataset updated. Retraining model...")
                subprocess.run(["python", "train_model.py"])
                print("\n Model updated!")

    except Exception as e:
        print(f" Training error: {e}")

# ---------------- LOAD MODEL ----------------
train_if_needed()

if os.path.exists(MODEL_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        print(f" AI Model '{MODEL_PATH}' loaded successfully!")
    except Exception as e:
        print(f" Error loading model: {e}")
else:
    print(" Model not available. Using fallback formula.")

# ---------------- ROUTE 1: LOG SENSOR DATA ----------------
@app.route('/data', methods=['POST'])
def receive_data():
    try:
        content = request.get_json()
        if not content:
            return jsonify({"error": "No data received"}), 400

        gas = float(content.get('gas', 0))
        temp = float(content.get('temperature', 0))
        hum = float(content.get('humidity', 0))

        # Clamp values
        gas = max(0, gas)
        temp = max(-50, min(temp, 100))
        hum = max(0, min(hum, 100))

        # Create AQI label
        aqi_label = (gas * 0.5) + (temp * 0.2) + (hum * 0.3)

        # Save to CSV
        file_exists = os.path.isfile(DATA_PATH)
        df = pd.DataFrame([[gas, temp, hum, aqi_label]],
                          columns=["gas", "temperature", "humidity", "AQI"])
        df.to_csv(DATA_PATH, mode='a', header=not file_exists, index=False)

        return jsonify({
            "status": "Data logged",
            "aqi_saved": round(aqi_label, 2)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- ROUTE 2: PREDICT & CONTROL ----------------
@app.route('/predict', methods=['POST'])
def predict():
    try:
        global last_data

        content = request.get_json()
        if not content:
            return jsonify({"error": "No data received"}), 400

        gas = float(content.get('gas', 0))
        temp = float(content.get('temperature', 0))
        hum = float(content.get('humidity', 0))

        # Clamp values
        gas = max(0, gas)
        temp = max(-50, min(temp, 100))
        hum = max(0, min(hum, 100))

        # ---------------- PREDICTION ----------------
        if model is not None:
            features = pd.DataFrame([[gas, temp, hum]],
                                    columns=["gas", "temperature", "humidity"])
            prediction = model.predict(features)[0]
            method = "RandomForest (AI)"
        else:
            prediction = (gas * 0.5) + (temp * 0.2) + (hum * 0.3)
            method = "Formula (Fallback)"

        # ---------------- CONTROL (FIXED) ----------------
        if prediction < 300:
            fan = 0
            fogger = 0
        elif prediction < 1000:
            fan = 1
            fogger = 0
        else:
            fan = 1
            fogger = 1

        # ---------------- STORE FOR DASHBOARD ----------------
        last_data = {
            "aqi": round(float(prediction), 2),
            "fan": fan,
            "fogger": fogger
        }

        # ---------------- CLEAN OUTPUT ----------------
        print(f"\n AQI: {prediction:.2f} | 🌀 Fan: {'ON' if fan else 'OFF'} | 💧 Fogger: {'ON' if fogger else 'OFF'}\n")

        return jsonify({
            "aqi_val": round(float(prediction), 2),
            "fan": fan,
            "fogger": fogger,
            "method_used": method
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- DASHBOARD DATA API ----------------
@app.route('/last')
def get_last():
    return jsonify(last_data)

# ---------------- LIVE DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
    <title> Air Quality Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    
    <style>
    body {
        font-family: 'Segoe UI';
        background: linear-gradient(to right, #0f172a, #1e293b);
        color: white;
        text-align: center;
    }
    
    h1 {
        margin-top: 20px;
        font-size: 30px;
    }
    
    .container {
        display: flex;
        justify-content: center;
        flex-wrap: wrap;
    }
    
    .card {
        background: #1e293b;
        margin: 15px;
        padding: 20px;
        border-radius: 20px;
        width: 200px;
        box-shadow: 0 0 10px rgba(0,0,0,0.4);
        transition: 0.3s;
    }
    
    .card:hover {
        transform: scale(1.05);
    }
    
    .value {
        font-size: 26px;
        margin-top: 10px;
    }
    
    .status {
        font-size: 20px;
    }
    
    /* Graph container */
    .graph-container {
        width: 80%;
        max-width: 700px;
        margin: 20px auto;
    }
    </style>
    </head>
    
    <body>
    
    <h1> Smart Indoor Air Quality System</h1>
    
    <div class="container">
    
    <div class="card">
        <h2>AQI</h2>
        <div id="aqi" class="value">--</div>
        <div id="level" style="font-size:18px;"></div>
    </div>
    
    <div class="card">
        <h2>Fan</h2>
        <div id="fan" class="status">--</div>
    </div>
    
    <div class="card">
        <h2>Fogger</h2>
        <div id="fog" class="status">--</div>
    </div>
    
    </div>
    
    <div class="graph-container">
        <canvas id="chart"></canvas>
    </div>
    
    <script>
    
    let aqiData = [];
    let labels = [];
    
    const ctx = document.getElementById('chart').getContext('2d');
    
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'AQI Trend',
                data: aqiData,
                borderColor: '#38bdf8',
                backgroundColor: 'rgba(56,189,248,0.2)',
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // AQI Level Function
    function getLevel(aqi) {
        if (aqi < 100) return ["Good 🌿", "#22c55e"];
        else if (aqi < 300) return ["Moderate 😐", "#facc15"];
        else return ["Danger 🚨", "#ef4444"];
    }
    
    async function loadData() {
        const res = await fetch('/last');
        const data = await res.json();
    
        document.getElementById('aqi').innerText = data.aqi;
    
        const [text, color] = getLevel(data.aqi);
        document.getElementById('level').innerHTML =
            "<span style='color:" + color + "; font-weight:bold'>" + text + "</span>";
    
        document.getElementById('fan').innerHTML =
            data.fan ? "🟢 ON" : "🔴 OFF";
    
        document.getElementById('fog').innerHTML =
            data.fogger ? "🟢 ON" : "🔴 OFF";
    
        // Add to graph
        const time = new Date().toLocaleTimeString();
    
        labels.push(time);
        aqiData.push(data.aqi);
    
        if (labels.length > 12) {
            labels.shift();
            aqiData.shift();
        }
    
        chart.update();
    }
    
    // Refresh every 2 seconds
    setInterval(loadData, 2000);
    loadData();
    
    </script>
    
    </body>
    </html>
    """
# ---------------- HEALTH CHECK ----------------
@app.route('/')
def home():
    return "Server is running with AI model!"

# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
