import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib
import os

DATA_PATH = "dataset.csv"
MODEL_PATH = "air_quality_model.pkl"

# 1. Load dataset
if not os.path.exists(DATA_PATH):
    print("❌ dataset.csv not found!")
    exit()

data = pd.read_csv(DATA_PATH)

# 2. Clean data
data = data.dropna(subset=["gas", "temperature", "humidity"])

# 3. Create AQI if missing
if "AQI" not in data.columns:
    print("⚠️ AQI not found. Creating synthetic AQI...")
    data["AQI"] = (
        data["gas"] * 0.5 +
        data["temperature"] * 0.2 +
        data["humidity"] * 0.3
    )

# 4. Features & Target
X = data[["gas", "temperature", "humidity"]]
y = data["AQI"]

# 5. Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# 6. Train model
model = RandomForestRegressor(
    n_estimators=100,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)

# 7. Evaluate
predictions = model.predict(X_test)

mse = mean_squared_error(y_test, predictions)
r2 = r2_score(y_test, predictions)

print("\n--- Model Evaluation ---")
print(f"MSE: {mse:.4f}")
print(f"R2 Score: {r2:.4f}")

# 8. Save model (FIXED NAME)
joblib.dump(model, MODEL_PATH)
print(f"\n✅ Model saved as '{MODEL_PATH}'")