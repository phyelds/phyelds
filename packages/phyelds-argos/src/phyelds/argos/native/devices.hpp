// The devices of any ARGoS robot, behind the few operations an aggregate round needs.
#pragma once
#include <argos3/core/control_interface/ci_controller.h>
#include <argos3/core/utility/datatypes/byte_array.h>
#include <argos3/core/utility/datatypes/color.h>
#include <argos3/core/utility/math/vector2.h>
#include <argos3/core/utility/math/vector3.h>
#include <argos3/plugins/robots/generic/control_interface/ci_positioning_sensor.h>
#include <functional>
#include <optional>
#include <vector>

namespace phyelds_argos {
// A frame from the radio; a range-and-bearing radio also measures where its sender is.
struct Heard {
    argos::CByteArray Data;
    std::optional<argos::CVector3> Offset; // metres, in the frame of the robot
};

// What a robot can do, from the devices its controller declares. A device the robot
// lacks is an empty function: its outputs are ignored, so one program fits a mixed swarm.
struct Devices {
    argos::CCI_PositioningSensor* Positioning = nullptr;
    bool Measures = false; // whether Receive measures where the senders are
    std::function<std::vector<Heard>()> Receive;
    std::function<void(argos::CByteArray const&)> Send; // an empty frame silences the radio
    std::function<argos::CVector2()> Obstacle; // repulsion, in the frame of the robot
    std::function<void(argos::CVector3 const&)> Drive; // m/s, in the global frame
    std::function<void(argos::CColor const&)> Light;
};

// Find the devices declared for a robot; it needs a radio and the positioning sensor.
Devices FindDevices(argos::CCI_Controller& robot);
}
