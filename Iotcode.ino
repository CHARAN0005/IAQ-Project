#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

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

  Serial.print("Connecting");

  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi Connected!");
  Serial.println(WiFi.localIP());
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

// -------- SEND DATA --------
void sendData(int gas, float temp, float hum)
{

  HTTPClient http;

  http.begin("http://192.168.1.75:5000/data"); // ✅ change based on YOUR system IP
  http.addHeader("Content-Type", "application/json");

  String json = "{";
  json += "\"gas\":" + String(gas) + ",";
  json += "\"temperature\":" + String(temp) + ",";
  json += "\"humidity\":" + String(hum);
  json += "}";

  int response = http.POST(json);

  Serial.print("Send: ");
  Serial.println(response);

  http.end();
}

// -------- GET PREDICTION --------
void getPrediction(int gas, float temp, float hum)
{

  HTTPClient http;

  http.begin("http://192.168.1.75:5000/predict"); // ✅ change based on YOUR system IP
  http.addHeader("Content-Type", "application/json");

  String json = "{";
  json += "\"gas\":" + String(gas) + ",";
  json += "\"temperature\":" + String(temp) + ",";
  json += "\"humidity\":" + String(hum);
  json += "}";

  http.POST(json);

  String response = http.getString();

  Serial.print("Control: ");
  Serial.println(response);

  // -------- ACTIVE LOW RELAY --------
  if (response.indexOf("\"fan\":1") > 0)
  {
    digitalWrite(RELAY_FAN, LOW); // ON
  }
  else
  {
    digitalWrite(RELAY_FAN, HIGH); // OFF
  }

  if (response.indexOf("\"fogger\":1") > 0)
  {
    digitalWrite(RELAY_FOG, LOW); // ON
  }
  else
  {
    digitalWrite(RELAY_FOG, HIGH); // OFF
  }

  http.end();
}

// -------- SETUP --------
void setup()
{

  Serial.begin(9600);

  pinMode(RELAY_FOG, OUTPUT);
  pinMode(RELAY_FAN, OUTPUT);

  // OFF initially (ACTIVE LOW)
  digitalWrite(RELAY_FOG, HIGH);
  digitalWrite(RELAY_FAN, HIGH);

  dht.begin();

  lcd.init();
  lcd.backlight();

  connectWiFi();
}

// -------- LOOP --------
void loop()
{

  int airValue = getGasValue();
  airValue = map(airValue, 0, 4095, 0, 1000);

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  Serial.print("Air Index: ");
  Serial.print(airValue);
  Serial.print(" | Temp: ");
  Serial.print(temperature);
  Serial.print(" | Hum: ");
  Serial.println(humidity);

  // LCD
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Air Index:");
  lcd.print(airValue);

  lcd.setCursor(0, 1);
  lcd.print("T:");
  lcd.print(temperature);
  lcd.print(" H:");
  lcd.print(humidity);

  // SEND + CONTROL
  sendData(airValue, temperature, humidity);
  getPrediction(airValue, temperature, humidity);

  delay(5000);
}