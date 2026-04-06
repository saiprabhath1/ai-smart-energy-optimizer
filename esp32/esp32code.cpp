#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "your wifi ssid";
const char* password = "your wifi password";

const char* serverURL = "http://type-ur-ip-address:port/get_energy_data"; //for flask

const int sensorPin = 34;        
const float sensitivity = 0.185; 
float zeroOffset = 2.5;          


float current = 0.0;
float power = 0.0;
float energy = 0.0;              
const float supplyVoltage = 9.0;
unsigned long lastSendTime = 0;
const unsigned long sendInterval = 1000; // 1 second


void calibrateSensor() {
  long sum = 0;
  const int samples = 500;
  Serial.println("\n Calibrating ACS712... (without 9v batt)");
  delay(2000);

  for (int i = 0; i < samples; i++) {
    sum += analogRead(sensorPin);
    delay(2);
  }
  float avg = sum / (float)samples;
  zeroOffset = (avg / 4095.0) * 3.3;
  Serial.print(" Zero offset calibrated at: ");
  Serial.print(zeroOffset, 3);
  Serial.println(" V");
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  Serial.print("\nConnecting to WiFi");

  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(1000);
  }

  Serial.println("\n WiFi connected");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  pinMode(sensorPin, INPUT);
  calibrateSensor();
}

void loop() {
  int sensorValue = analogRead(sensorPin);
  float voltage = (sensorValue / 4095.0) * 3.3;

  current = (voltage - zeroOffset) / sensitivity;
  if (abs(current) < 0.03) current = 0.0; 

//pow for is v*i here v is 9
  power = current * supplyVoltage; 
  energy += (power / 3600000.0);   

 //for ser monitor
  Serial.print("I: ");
  Serial.print(current, 3);
  Serial.print(" A | P: ");
  Serial.print(power, 2);
  Serial.print(" W | E: ");
  Serial.print(energy, 6);
  Serial.println(" kWh");

  
  if (millis() - lastSendTime >= sendInterval) {
    lastSendTime = millis();

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(serverURL);
      http.addHeader("Content-Type", "application/json");

      // for json 
      String payload = "{\"current_usage\": " + String(current, 3) +
                       ", \"power\": " + String(power, 2) +
                       ", \"energy_usage\": " + String(energy, 6) + "}";

      int httpCode = http.POST(payload);

      if (httpCode > 0) {
        Serial.println("Data sent to Flask");
        Serial.println(http.getString());
      } else {
        Serial.print("Error sending data: ");
        Serial.println(httpCode);
      }

      http.end();
    } else {
      Serial.println("WiFi is disconnected");
    }
  }

  delay(200);
}
