// =============================================================================
//  main.cpp - ESP32 actuator controller for the auto-aiming trashcan.
//
//  The UNO Q does the seeing (USB camera + YOLOX-nano). This board does the
//  moving. They talk over WiFi - both boards sit on the same network, so the
//  trashcan is not tethered to anything and can actually drive around.
//
//  The joke: the lid sits OPEN, inviting. The moment something is actually
//  thrown at it, the lid SLAMS SHUT and the trashcan refuses the rubbish.
//  It reopens a few seconds later to bait the next person.
//
//  COMMANDS (identical over WiFi and serial - one parser, two transports)
//    AIM <offset>   offset -1.0 (target hard left) .. +1.0 (hard right).
//                   0 drives straight. Steers the wheels toward the target.
//    THROWN         something was thrown in -> slam the lid shut, refuse it.
//    OPEN           reopen the lid (bait reset).
//    STOP           stop the wheels.
//    LID <angle>    drive the lid servo to a raw angle. Calibration aid:
//                   use it to find your real OPEN/CLOSED angles.
//    PING           replies "PONG". Link check.
//
//  OVER WIFI    GET http://<ip>/cmd?c=THROWN
//               GET http://<ip>/         control page, works from a phone
//  OVER SERIAL  type the command at 115200 baud
//
//  WIRING
//    L298N  ENA 18  ENB 19  IN1 27  IN2 26  IN3 25  IN4 33
//    Lid servo signal -> GPIO 16, servo V+ -> its own 5V supply (NOT the
//    ESP32 3V3 pin), servo GND -> common ground with the ESP32.
// =============================================================================
#include <Arduino.h>
#include <ESP32Servo.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include "secrets.h"

// ---- Motor driver (L298N) ---------------------------------------------------
const int ENA = 18;
const int ENB = 19;
const int IN1 = 27;
const int IN2 = 26;
const int IN3 = 25;
const int IN4 = 33;

// Motor PWM lives on LEDC channels 4/5 (timer 2). ESP32Servo gets timer 0,
// allocated in setup(). Keeping them on separate timers stops the servo from
// jittering every time the motor duty changes.
const int PWM_CH_A = 4;
const int PWM_CH_B = 5;
const int PWM_FREQ = 5000;
const int PWM_RES  = 8;

const int DRIVE_SPEED = 200;   // 0-255. Steering is bang-bang at this duty.

// Motor B measured slower than Motor A on this build at equal duty. Scale B up
// to match. 1.00 = no correction; raise until both wheels turn at the same rate.
const float MOTOR_B_TRIM = 1.00f;

// ---- Lid servo --------------------------------------------------------------
const int LID_SERVO_PIN = 16;

// Calibrate these from the web page slider, then set them here.
const int LID_OPEN_ANGLE   = 90;
const int LID_CLOSED_ANGLE = 0;

const uint16_t SERVO_MIN_US = 500;
const uint16_t SERVO_MAX_US = 2400;

// The lid slams shut fast (that is the gag) but reopens lazily.
const uint16_t LID_CLOSE_MS = 180;
const uint16_t LID_OPEN_MS  = 900;

// How long the lid stays shut before reopening to bait the next person.
const uint32_t LID_SHUT_HOLD_MS = 4000;

// Stop the wheels if the UNO Q goes quiet - never keep driving blind.
const uint32_t AIM_TIMEOUT_MS = 1000;

Servo     lidServo;
WebServer server(80);

enum LidState : uint8_t { LID_IDLE, LID_MOVING, LID_SHUT_WAITING };

LidState lidState   = LID_IDLE;
float    lidAngle   = LID_OPEN_ANGLE;
float    lidFrom    = LID_OPEN_ANGLE;
float    lidTo      = LID_OPEN_ANGLE;
uint32_t lidStarted = 0;
uint16_t lidSegment = 1;
uint32_t lidShutAt  = 0;

float    aimOffset = 0.0f;
bool     aimActive = false;
uint32_t lastAimAt = 0;

String   inputLine;

// ---- Motors -----------------------------------------------------------------
void motorA(int speed, bool forward) {
    digitalWrite(IN1, forward ? HIGH : LOW);
    digitalWrite(IN2, forward ? LOW : HIGH);
    ledcWrite(PWM_CH_A, constrain(speed, 0, 255));
}

void motorB(int speed, bool forward) {
    digitalWrite(IN3, forward ? HIGH : LOW);
    digitalWrite(IN4, forward ? LOW : HIGH);
    ledcWrite(PWM_CH_B, constrain((int)(speed * MOTOR_B_TRIM), 0, 255));
}

void stopMotors() {
    ledcWrite(PWM_CH_A, 0);
    ledcWrite(PWM_CH_B, 0);
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, LOW);
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, LOW);
}

void steer(float offset) {
    const float deadzone = 0.12f;
    if (offset < -deadzone) {        // target left: pivot left
        motorA(DRIVE_SPEED, false);
        motorB(DRIVE_SPEED, true);
    } else if (offset > deadzone) {  // target right: pivot right
        motorA(DRIVE_SPEED, true);
        motorB(DRIVE_SPEED, false);
    } else {                         // centered: close in
        motorA(DRIVE_SPEED, true);
        motorB(DRIVE_SPEED, true);
    }
}

// ---- Lid --------------------------------------------------------------------
static inline float ease(float t) {
    if (t <= 0.0f) return 0.0f;
    if (t >= 1.0f) return 1.0f;
    return 0.5f * (1.0f - cosf((float)M_PI * t));
}

void moveLid(int target, uint16_t durationMs) {
    lidFrom    = lidAngle;
    lidTo      = constrain(target, 0, 180);
    lidSegment = durationMs ? durationMs : 1;
    lidStarted = millis();
    lidState   = LID_MOVING;
}

void updateLid() {
    if (lidState == LID_MOVING) {
        const uint32_t elapsed = millis() - lidStarted;
        const float t = ease((float)elapsed / (float)lidSegment);
        lidAngle = lidFrom + t * (lidTo - lidFrom);
        lidServo.write((int)lroundf(lidAngle));

        if (elapsed >= lidSegment) {
            lidAngle = lidTo;
            lidServo.write((int)lroundf(lidAngle));
            // Shutting the lid starts the hold timer that later reopens it.
            if ((int)lroundf(lidTo) == LID_CLOSED_ANGLE) {
                lidState  = LID_SHUT_WAITING;
                lidShutAt = millis();
            } else {
                lidState = LID_IDLE;
            }
        }
    } else if (lidState == LID_SHUT_WAITING) {
        if (millis() - lidShutAt >= LID_SHUT_HOLD_MS) {
            Serial.println("EVT reopening");
            moveLid(LID_OPEN_ANGLE, LID_OPEN_MS);
        }
    }
}

// ---- Command handling (shared by WiFi and serial) ---------------------------
String handleCommand(String line) {
    line.trim();
    if (line.length() == 0) return "ERR empty";

    if (line.startsWith("AIM")) {
        aimOffset = line.substring(3).toFloat();
        aimActive = true;
        lastAimAt = millis();
        return "OK AIM " + String(aimOffset, 3);

    } else if (line == "THROWN") {
        // The whole point of the machine.
        moveLid(LID_CLOSED_ANGLE, LID_CLOSE_MS);
        aimActive = false;
        stopMotors();
        return "OK THROWN lid=closed";

    } else if (line == "OPEN") {
        moveLid(LID_OPEN_ANGLE, LID_OPEN_MS);
        return "OK OPEN";

    } else if (line == "STOP") {
        aimActive = false;
        stopMotors();
        return "OK STOP";

    } else if (line.startsWith("LID")) {
        const int angle = line.substring(3).toInt();
        moveLid(angle, LID_OPEN_MS);
        return "OK LID " + String(angle);

    } else if (line == "PING") {
        return "PONG";
    }

    return "ERR unknown: " + line;
}

void readSerial() {
    while (Serial.available()) {
        const char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (inputLine.length()) {
                Serial.println(handleCommand(inputLine));
                inputLine = "";
            }
        } else if (inputLine.length() < 64) {
            inputLine += c;
        }
    }
}

// ---- HTTP -------------------------------------------------------------------
const char CONTROL_PAGE[] PROGMEM = R"HTML(<!doctype html>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Trashcan</title>
<style>
body{font-family:system-ui;margin:0;padding:24px;background:#111;color:#eee}
h1{font-size:1.2rem;margin:0 0 4px}p{color:#888;margin:0 0 20px;font-size:.85rem}
button{display:block;width:100%;padding:16px;margin:8px 0;font-size:1rem;
border:0;border-radius:10px;background:#2a2a2a;color:#eee}
button.slam{background:#7a1f1f}
input{width:100%}label{font-size:.85rem;color:#888}
#out{margin-top:16px;padding:10px;background:#000;border-radius:8px;
font-family:monospace;font-size:.8rem;color:#6f6;min-height:1.2em}
</style>
<h1>Auto-aiming trashcan</h1>
<p>Manual override / servo calibration</p>
<button class=slam onclick="c('THROWN')">SLAM LID (refuse)</button>
<button onclick="c('OPEN')">Open lid</button>
<button onclick="c('STOP')">Stop wheels</button>
<label>Lid angle: <span id=a>90</span>&deg;</label>
<input type=range min=0 max=180 value=90 oninput="a.textContent=this.value"
onchange="c('LID '+this.value)">
<div id=out>ready</div>
<script>
function c(x){fetch('/cmd?c='+encodeURIComponent(x))
.then(r=>r.text()).then(t=>out.textContent=t)
.catch(e=>out.textContent='ERR '+e)}
</script>)HTML";

void handleRoot() {
    server.send_P(200, "text/html", CONTROL_PAGE);
}

void handleCmd() {
    if (!server.hasArg("c")) {
        server.send(400, "text/plain", "ERR missing c parameter");
        return;
    }
    const String reply = handleCommand(server.arg("c"));
    server.send(200, "text/plain", reply);
}

void handleStatus() {
    String s = "{\"lid\":" + String((int)lroundf(lidAngle));
    s += ",\"aim\":" + String(aimOffset, 3);
    s += ",\"driving\":" + String(aimActive ? "true" : "false");
    s += ",\"rssi\":" + String(WiFi.RSSI()) + "}";
    server.send(200, "application/json", s);
}

void setup() {
    Serial.begin(115200);

    pinMode(IN1, OUTPUT);
    pinMode(IN2, OUTPUT);
    pinMode(IN3, OUTPUT);
    pinMode(IN4, OUTPUT);
    ledcSetup(PWM_CH_A, PWM_FREQ, PWM_RES);
    ledcSetup(PWM_CH_B, PWM_FREQ, PWM_RES);
    ledcAttachPin(ENA, PWM_CH_A);
    ledcAttachPin(ENB, PWM_CH_B);
    stopMotors();

    ESP32PWM::allocateTimer(0);
    lidServo.setPeriodHertz(50);
    lidServo.attach(LID_SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
    lidAngle = LID_OPEN_ANGLE;
    lidServo.write(LID_OPEN_ANGLE);

    Serial.println();
    Serial.println("BOOT auto-aiming-trashcan esp32 actuators");

    // WiFi is how the UNO Q talks to us, but a failure here must not take the
    // machine down: serial still accepts every command.
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("WIFI connecting to ");
    Serial.print(WIFI_SSID);
    const uint32_t startedAt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startedAt < 20000) {
        delay(250);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("WIFI ok  ip=");
        Serial.print(WiFi.localIP());
        Serial.print("  rssi=");
        Serial.println(WiFi.RSSI());
        if (MDNS.begin("trashcan")) {
            MDNS.addService("http", "tcp", 80);
            Serial.println("MDNS trashcan.local");
        }
    } else {
        Serial.println("WIFI failed - serial commands still work");
    }

    server.on("/", handleRoot);
    server.on("/cmd", handleCmd);
    server.on("/status", handleStatus);
    server.begin();

    Serial.println("READY cmds: AIM <-1..1> | THROWN | OPEN | STOP | LID <angle> | PING");
}

void loop() {
    server.handleClient();
    readSerial();
    updateLid();

    // Wheels only run while the UNO Q keeps saying where to go.
    if (aimActive && millis() - lastAimAt <= AIM_TIMEOUT_MS) {
        steer(aimOffset);
    } else {
        if (aimActive) {
            aimActive = false;
            Serial.println("EVT aim timeout, motors stopped");
        }
        stopMotors();
    }
}
