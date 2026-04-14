#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>

// -------- WIFI --------
const char *ssid = "Wifiname";
const char *password = "password";

// -------- PINS --------
#define MQ135_PIN 34
#define DHT_PIN 4
#define DHTTYPE DHT11

#define RELAY_FOG 18
#define RELAY_FAN 5

// -------- OBJECTS --------
DHT dht(DHT_PIN, DHTTYPE);
LiquidCrystal_I2C lcd(0x27, 16, 2);

// -------- WIFI --------
void connectWiFi()
{
  WiFi.begin(ssid, password);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Connecting WiFi");

  int dots = 0;

  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
    lcd.setCursor(dots, 1);
    lcd.print(".");
    dots++;

    if (dots > 15)
    {
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Connecting WiFi");
      dots = 0;
    }
  }

  Serial.println("\nWiFi Connected!");
  Serial.println(WiFi.localIP());

  // Connected message
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("WiFi Connected");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.localIP());

  delay(2000);
}
// -------- GAS SMOOTHING --------
int getGasValue()
{
  int sum = 0;
  for (int i = 0; i < 10; i++)
  {
    sum += analogRead(MQ135_PIN);
    delay(10);
  }
  return sum / 10;
}

// -------- GET PREDICTION + LCD + RELAY --------
void getPrediction(int gas, float temp, float hum)
{
  HTTPClient http;

  http.begin("http://197.20.10.4:5000/predict");//ip
  http.addHeader("Content-Type", "application/json");

  String json = "{";
  json += "\"gas\":" + String(gas) + ",";
  json += "\"temperature\":" + String(temp) + ",";
  json += "\"humidity\":" + String(hum);
  json += "}";

  int httpResponse = http.POST(json);

  if (httpResponse > 0)
  {
    String response = http.getString();

    Serial.println("Server Response:");
    Serial.println(response);

    // -------- PARSE JSON --------
    StaticJsonDocument<200> doc;
    DeserializationError error = deserializeJson(doc, response);

    if (!error)
    {
      float aqi = doc["aqi_val"];
      int fan = doc["fan"];
      int fog = doc["fogger"];

      // -------- RELAY CONTROL --------
      digitalWrite(RELAY_FAN, fan ? LOW : HIGH);
      digitalWrite(RELAY_FOG, fog ? LOW : HIGH);

      // -------- LCD DISPLAY --------
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("AQI:");
      lcd.print((int)aqi);
    

      lcd.setCursor(0, 1);
      lcd.print("T:");
      lcd.print(temp);
      lcd.print(" H:");
      lcd.print(hum);

      // -------- DEBUG --------
      Serial.print("LCD AQI: ");
      Serial.println(aqi);
    }
    else
    {
      Serial.println("JSON Parse Error!");
    }
  }
  else
  {
    Serial.println("HTTP Error!");
  }

  http.end();
}

// -------- SETUP --------
void setup()
{
  Serial.begin(9600);

  pinMode(RELAY_FOG, OUTPUT);
  pinMode(RELAY_FAN, OUTPUT);

  // ACTIVE LOW → OFF initially
  digitalWrite(RELAY_FOG, HIGH);
  digitalWrite(RELAY_FAN, HIGH);

  dht.begin();

  lcd.init();
  lcd.backlight();
  // INITIAL MESSAGE
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Air Quality");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");

  delay(2000);

  connectWiFi();
}

// -------- LOOP --------
void loop()
{
  // SENSOR READ
  int gasRaw = getGasValue();
  int gas = map(gasRaw, 0, 4095, 0, 1000);

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  Serial.print("Gas: ");
  Serial.print(gas);
  Serial.print(" | Temp: ");
  Serial.print(temperature);
  Serial.print(" | Hum: ");
  Serial.println(humidity);

  // ONE API CALL
  getPrediction(gas, temperature, humidity);

  delay(5000);
}
