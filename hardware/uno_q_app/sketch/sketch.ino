// =============================================================================
//  sketch.ino - MCU side of the Object & Human Detection app.
//
//  The Python brick (python/main.py) runs a YOLOX-nano model against the USB
//  camera feed and picks whichever detection (person, or any COCO object) is
//  closest to the frame center. It reports a normalized horizontal offset in
//  [-1, 1] to this sketch over the Bridge, and this code steers two DC motors
//  (through an H-bridge driver, e.g. L298N) so the trashcan turns toward it.
//
//  offset < 0        -> target left of center  -> turn left
//  offset > 0        -> target right of center -> turn right
//  offset == 0       -> target centered, or none in view -> drive straight
//  no update in time -> assume the Python side stalled -> stop (fail safe)
//
//  PIN NAMES BELOW ARE UNVERIFIED - D2/D3/D4/D5 follow the standard Arduino
//  Uno digital header convention, but this sketch has not been run against
//  real UNO Q hardware. Check them against the official UNO Q pinout before
//  wiring, and adjust to match your actual H-bridge IN1-IN4 connections.
//  No PWM/speed control is used here (bang-bang steering) - this is a
//  minimal bring-up, not a tuned drive system.
// =============================================================================
#include <Arduino_RouterBridge.h>

const int LEFT_IN1  = D2;
const int LEFT_IN2  = D3;
const int RIGHT_IN1 = D4;
const int RIGHT_IN2 = D5;

// If no target update arrives for this long, assume the Python side has
// stalled or lost the camera, and stop rather than keep driving blind.
const unsigned long TARGET_TIMEOUT_MS = 1000;

volatile float         g_offset     = 0.0f;
volatile bool          g_present    = false;
volatile unsigned long g_lastUpdate = 0;

void driveLeft(bool forward) {
    digitalWrite(LEFT_IN1, forward ? HIGH : LOW);
    digitalWrite(LEFT_IN2, forward ? LOW  : HIGH);
}

void driveRight(bool forward) {
    digitalWrite(RIGHT_IN1, forward ? HIGH : LOW);
    digitalWrite(RIGHT_IN2, forward ? LOW  : HIGH);
}

void stopMotors() {
    digitalWrite(LEFT_IN1, LOW);
    digitalWrite(LEFT_IN2, LOW);
    digitalWrite(RIGHT_IN1, LOW);
    digitalWrite(RIGHT_IN2, LOW);
}

// Called by the Python side's set_target() (arduino.app_utils.notify()) on
// every detection update. Registered via provide_safe, so this only ever
// runs from the main loop thread - never concurrently with loop() itself.
bool set_target(float offset, bool present) {
    g_offset     = offset;
    g_present    = present;
    g_lastUpdate = millis();
    return true;
}

void setup() {
    Bridge.begin();
    Monitor.begin(115200);

    pinMode(LEFT_IN1, OUTPUT);
    pinMode(LEFT_IN2, OUTPUT);
    pinMode(RIGHT_IN1, OUTPUT);
    pinMode(RIGHT_IN2, OUTPUT);
    stopMotors();

    Bridge.provide_safe("set_target", set_target);
}

void loop() {
    if (!g_present || millis() - g_lastUpdate > TARGET_TIMEOUT_MS) {
        stopMotors();
        return;
    }

    if (g_offset < 0) {
        driveLeft(false);
        driveRight(true);
    } else if (g_offset > 0) {
        driveLeft(true);
        driveRight(false);
    } else {
        driveLeft(true);
        driveRight(true);
    }
}
