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
            print("⚠️ Model not found. Training now...")
            subprocess.run(["python", "train_model.py"])
            print("✅ Training completed!")

        elif os.path.exists(DATA_PATH):
            model_time = os.path.getmtime(MODEL_PATH)
            data_time = os.path.getmtime(DATA_PATH)

            if data_time > model_time:
                print("📊 Dataset updated. Retraining model...")
                subprocess.run(["python", "train_model.py"])
                print("✅ Model updated!")

    except Exception as e:
        print(f"❌ Training error: {e}")

# ---------------- LOAD MODEL ----------------
train_if_needed()

if os.path.exists(MODEL_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        print(f"✅ AI Model '{MODEL_PATH}' loaded successfully!")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
else:
    print("⚠️ Model not available. Using fallback formula.")

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
        print(f"\n🌫️ AQI: {prediction:.2f} | 🌀 Fan: {'ON' if fan else 'OFF'} | 💧 Fogger: {'ON' if fogger else 'OFF'}\n")

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
                font-family: Arial;
                text-align: center;
                background: #0f172a;
                color: white;
            }
            .card {
                background: #1e293b;
                padding: 20px;
                margin: 20px;
                border-radius: 15px;
                display: inline-block;
                width: 200px;
            }
            h1 { color: #38bdf8; }
            .good { color: #22c55e; }
            .moderate { color: #facc15; }
            .danger { color: #ef4444; }
        </style>
    </head>
    <body>

        <h1> Smart Air Quality Dashboard</h1>

        <div class="card">
            <h2>AQI</h2>
            <p id="aqi">--</p>
            <p id="level"></p>
        </div>

        <div class="card">
            <h2>Fan</h2>
            <p id="fan">--</p>
        </div>

        <div class="card">
            <h2>Fogger</h2>
            <p id="fog">--</p>
        </div>

        <canvas id="chart" width="600" height="300"></canvas>

        <script>
            let aqiData = [];
            let labels = [];

            const ctx = document.getElementById('chart').getContext('2d');

            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'AQI',
                        data: aqiData,
                        borderWidth: 2,
                        fill: false
                    }]
                },
                options: {
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });

            function getLevel(aqi) {
                if (aqi < 200) return ["Good", "good"];
                else if (aqi < 400) return ["Moderate", "moderate"];
                else return ["Danger", "danger"];
            }

            async function loadData() {
                const res = await fetch('/last');
                const data = await res.json();

                document.getElementById('aqi').innerText = data.aqi;

                const [text, cls] = getLevel(data.aqi);
                document.getElementById('level').innerHTML =
                    "<span class='" + cls + "'>" + text + "</span>";

                document.getElementById('fan').innerText =
                    data.fan ? "ON" : "OFF";

                document.getElementById('fog').innerText =
                    data.fogger ? "ON" : "OFF";

                // Add to chart
                const time = new Date().toLocaleTimeString();

                labels.push(time);
                aqiData.push(data.aqi);

                if (labels.length > 10) {
                    labels.shift();
                    aqiData.shift();
                }

                chart.update();
            }

            setInterval(loadData, 2000);
            loadData();
        </script>

    </body>
    </html>
    """

# ---------------- HEALTH CHECK ----------------
@app.route('/')
def home():
    return "✅ Server is running with AI model!"

# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)