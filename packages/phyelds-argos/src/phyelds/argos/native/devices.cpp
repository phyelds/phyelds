#include "devices.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <utility>
#include <argos3/plugins/robots/builderbot/control_interface/ci_builderbot_differential_drive_actuator.h>
#include <argos3/plugins/robots/builderbot/control_interface/ci_builderbot_leds_actuator.h>
#include <argos3/plugins/robots/builderbot/control_interface/ci_builderbot_rangefinders_sensor.h>
#include <argos3/plugins/robots/drone/control_interface/ci_drone_flight_system_actuator.h>
#include <argos3/plugins/robots/drone/control_interface/ci_drone_flight_system_sensor.h>
#include <argos3/plugins/robots/drone/control_interface/ci_drone_leds_actuator.h>
#include <argos3/plugins/robots/e-puck/control_interface/ci_epuck_proximity_sensor.h>
#include <argos3/plugins/robots/eye-bot/control_interface/ci_eyebot_proximity_sensor.h>
#include <argos3/plugins/robots/foot-bot/control_interface/ci_footbot_proximity_sensor.h>
#include <argos3/plugins/robots/generic/control_interface/ci_differential_steering_actuator.h>
#include <argos3/plugins/robots/generic/control_interface/ci_directional_leds_actuator.h>
#include <argos3/plugins/robots/generic/control_interface/ci_leds_actuator.h>
#include <argos3/plugins/robots/generic/control_interface/ci_quadrotor_speed_actuator.h>
#include <argos3/plugins/robots/generic/control_interface/ci_range_and_bearing_actuator.h>
#include <argos3/plugins/robots/generic/control_interface/ci_range_and_bearing_sensor.h>
#include <argos3/plugins/robots/generic/control_interface/ci_simple_radios_actuator.h>
#include <argos3/plugins/robots/generic/control_interface/ci_simple_radios_sensor.h>
#include <argos3/plugins/robots/pi-puck/control_interface/ci_pipuck_differential_drive_actuator.h>
#include <argos3/plugins/robots/pi-puck/control_interface/ci_pipuck_leds_actuator.h>
#include <argos3/plugins/robots/pi-puck/control_interface/ci_pipuck_rangefinders_sensor.h>

using namespace argos;

namespace phyelds_argos {
namespace {
constexpr Real CM_PER_M = 100; // range-and-bearing ranges and differential_steering speeds are in cm
constexpr Real BUILDERBOT_RANGE = 0.05; // what its rangefinders report when they see nothing

CRadians Yaw(CCI_PositioningSensor const* positioning) {
    CRadians yaw, pitch, roll;
    positioning->GetReading().Orientation.ToEulerAngles(yaw, pitch, roll);
    return yaw;
}

// Wheel speeds (m/s) that turn a differential drive towards a velocity in its own frame,
// and drive it forward as its heading aligns.
std::pair<Real, Real> Wheels(CVector2 const& velocity) {
    Real speed = velocity.Length();
    if (speed < 0.005) return {0, 0};
    Real angle = velocity.Angle().GetValue();
    Real forward = speed * std::max<Real>(0, std::cos(angle));
    Real turn = speed * angle;
    return {forward - turn, forward + turn};
}

// A rangefinder distance as a proximity reading: exp(-distance) in range, as ARGoS
// computes the readings of the foot-bot, e-puck and eye-bot, and 0 beyond it.
Real Closeness(Real distance, Real range) {
    return distance < range ? std::exp(-distance) : 0;
}

// The horizontal direction a rangefinder looks along, in the frame of the robot.
CVector2 Looking(CQuaternion const& orientation) {
    CVector3 ray(CVector3::Z);
    ray.Rotate(orientation);
    return {ray.GetX(), ray.GetY()};
}

// The repulsion of a ring of proximity sensors with angles, as the foot-bot's.
template <class Sensor> std::function<CVector2()> Ring(Sensor* sensor) {
    return [sensor] {
        CVector2 repulsion;
        for (auto const& reading : sensor->GetReadings()) repulsion -= CVector2(reading.Value, reading.Angle);
        return repulsion;
    };
}

void FindRadio(CCI_Controller& robot, Devices& devices) {
    if (robot.HasActuator("range_and_bearing")) {
        auto* out = robot.GetActuator<CCI_RangeAndBearingActuator>("range_and_bearing");
        auto* in = robot.GetSensor<CCI_RangeAndBearingSensor>("range_and_bearing");
        devices.Measures = true;
        devices.Receive = [in] {
            std::vector<Heard> heard;
            for (auto const& packet : in->GetReadings()) {
                CVector3 offset;
                offset.FromSphericalCoords(packet.Range / CM_PER_M,
                    CRadians::PI_OVER_TWO - packet.VerticalBearing, packet.HorizontalBearing);
                heard.push_back({packet.Data, offset});
            }
            return heard;
        };
        devices.Send = [out](CByteArray const& frame) {
            if (frame.Size() > out->GetSize())
                throw std::runtime_error("payload of " + std::to_string(frame.Size() - 6)
                    + " bytes exceeds rab_data_size (including 6-byte header)");
            CByteArray data(frame);
            data.Resize(out->GetSize());
            out->SetData(data);
        };
    } else if (robot.HasActuator("simple_radios")) {
        auto* out = robot.GetActuator<CCI_SimpleRadiosActuator>("simple_radios");
        auto* in = robot.GetSensor<CCI_SimpleRadiosSensor>("simple_radios");
        // Every interface: a block has a radio on each face, a BuilderBot both wifi and NFC.
        devices.Receive = [in] {
            std::vector<Heard> heard;
            for (auto const& interface : in->GetInterfaces())
                for (auto const& message : interface.Messages) heard.push_back({message, std::nullopt});
            return heard;
        };
        devices.Send = [out](CByteArray const& frame) {
            if (frame.Size() == 0) return; // simple radios send each message once
            for (auto& interface : out->GetInterfaces()) interface.Messages.push_back(frame);
        };
    } else {
        throw std::runtime_error("the robot needs a range_and_bearing or a simple_radios radio");
    }
}

void FindLocomotion(CCI_Controller& robot, Devices& devices) {
    auto* positioning = devices.Positioning;
    auto local = [positioning](CVector3 const& velocity) {
        return CVector2(velocity.GetX(), velocity.GetY()).Rotate(-Yaw(positioning));
    };
    if (robot.HasActuator("differential_steering")) {
        auto* wheels = robot.GetActuator<CCI_DifferentialSteeringActuator>("differential_steering");
        devices.Drive = [wheels, local](CVector3 const& velocity) {
            auto [left, right] = Wheels(local(velocity));
            wheels->SetLinearVelocity(left * CM_PER_M, right * CM_PER_M);
        };
    } else if (robot.HasActuator("pipuck_differential_drive")) {
        auto* wheels = robot.GetActuator<CCI_PiPuckDifferentialDriveActuator>("pipuck_differential_drive");
        devices.Drive = [wheels, local](CVector3 const& velocity) {
            auto [left, right] = Wheels(local(velocity));
            wheels->SetLinearVelocity(left, right);
        };
    } else if (robot.HasActuator("builderbot_differential_drive")) {
        auto* wheels = robot.GetActuator<CCI_BuilderBotDifferentialDriveActuator>("builderbot_differential_drive");
        // Its right wheel is mirrored: (v, -v) drives the BuilderBot straight ahead.
        devices.Drive = [wheels, local](CVector3 const& velocity) {
            auto [left, right] = Wheels(local(velocity));
            wheels->SetTargetVelocityLeft(left);
            wheels->SetTargetVelocityRight(-right);
        };
    } else if (robot.HasActuator("quadrotor_speed")) {
        auto* rotors = robot.GetActuator<CCI_QuadRotorSpeedActuator>("quadrotor_speed");
        devices.Drive = [rotors](CVector3 const& velocity) { rotors->SetLinearVelocity(velocity); };
    } else if (robot.HasActuator("drone_flight_system")) {
        auto* flight = robot.GetActuator<CCI_DroneFlightSystemActuator>("drone_flight_system");
        auto* state = robot.GetSensor<CCI_DroneFlightSystemSensor>("drone_flight_system");
        // The flight system flies towards a target, in the frame the drone started in, at
        // 1/s of the distance: a target one second ahead is flown at the velocity. At zero
        // velocity the drone keeps its last target, so it holds its place without drifting.
        devices.Drive = [flight, state, positioning](CVector3 velocity) {
            if (velocity == CVector3::ZERO) return;
            velocity.RotateZ(CRadians(state->GetOrientation().GetZ()) - Yaw(positioning));
            flight->SetTargetPosition(state->GetPosition() + velocity);
        };
    }
}

void FindObstacles(CCI_Controller& robot, Devices& devices) {
    if (robot.HasSensor("footbot_proximity")) {
        devices.Obstacle = Ring(robot.GetSensor<CCI_FootBotProximitySensor>("footbot_proximity"));
    } else if (robot.HasSensor("epuck_proximity")) {
        devices.Obstacle = Ring(robot.GetSensor<CCI_EPuckProximitySensor>("epuck_proximity"));
    } else if (robot.HasSensor("eyebot_proximity")) {
        devices.Obstacle = Ring(robot.GetSensor<CCI_EyeBotProximitySensor>("eyebot_proximity"));
    } else if (robot.HasSensor("pipuck_rangefinders")) {
        auto* sensor = robot.GetSensor<CCI_PiPuckRangefindersSensor>("pipuck_rangefinders");
        devices.Obstacle = [sensor] {
            CVector2 repulsion;
            sensor->Visit([&repulsion](auto const& rangefinder) {
                auto const& [anchor, position, orientation, range] = rangefinder.Configuration;
                repulsion -= Looking(orientation) * Closeness(rangefinder.Proximity, range);
            });
            return repulsion;
        };
    } else if (robot.HasSensor("builderbot_rangefinders")) {
        auto* sensor = robot.GetSensor<CCI_BuilderBotRangefindersSensor>("builderbot_rangefinders");
        devices.Obstacle = [sensor] {
            CVector2 repulsion;
            // The ring on its body, but for the front pair (6, 7) that faces its own end
            // effector, as do the rangefinders on the end effector.
            for (auto const* rangefinder : sensor->GetInterfaces())
                if (rangefinder->Anchor == "origin" && rangefinder->Label != "6" && rangefinder->Label != "7")
                    repulsion -= Looking(rangefinder->OrientationOffset)
                        * Closeness(rangefinder->Proximity, BUILDERBOT_RANGE);
            return repulsion;
        };
    }
}

void FindLights(CCI_Controller& robot, Devices& devices) {
    if (robot.HasActuator("leds")) {
        auto* leds = robot.GetActuator<CCI_LEDsActuator>("leds");
        devices.Light = [leds](CColor const& color) { leds->SetAllColors(color); };
    } else if (robot.HasActuator("directional_leds")) {
        auto* leds = robot.GetActuator<CCI_DirectionalLEDsActuator>("directional_leds");
        devices.Light = [leds](CColor const& color) { leds->SetAllColors(color); };
    } else if (robot.HasActuator("builderbot_leds")) {
        auto* leds = robot.GetActuator<CCI_BuilderBotLEDsActuator>("builderbot_leds");
        devices.Light = [leds](CColor const& color) { leds->SetLEDs(color); };
    } else if (robot.HasActuator("drone_leds")) {
        auto* leds = robot.GetActuator<CCI_DroneLEDsActuator>("drone_leds");
        devices.Light = [leds](CColor const& color) { leds->SetLEDs(color); };
    } else if (robot.HasActuator("pipuck_leds")) {
        // The Pi-Puck ring LEDs are only on or off.
        auto* leds = robot.GetActuator<CCI_PiPuckLEDsActuator>("pipuck_leds");
        devices.Light = [leds](CColor const& color) { leds->SetRingLEDs(color != CColor::BLACK); };
    }
}
}

Devices FindDevices(CCI_Controller& robot) {
    Devices devices;
    devices.Positioning = robot.GetSensor<CCI_PositioningSensor>("positioning");
    FindRadio(robot, devices);
    FindLocomotion(robot, devices);
    FindObstacles(robot, devices);
    FindLights(robot, devices);
    return devices;
}
}
