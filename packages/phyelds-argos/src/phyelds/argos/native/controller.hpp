// Native host only: all aggregate state and serialization belong to phyelds Device.
#pragma once
#include <argos3/core/control_interface/ci_controller.h>
#include <argos3/core/utility/datatypes/color.h>
#include <argos3/core/utility/math/vector2.h>
#include <string>

namespace argos {
class CCI_DifferentialSteeringActuator;
class CCI_LEDsActuator;
class CCI_RangeAndBearingActuator;
class CCI_RangeAndBearingSensor;
class CCI_PositioningSensor;
class CCI_FootBotProximitySensor;
}
struct _object;

class CPhyeldsController : public argos::CCI_Controller {
public:
    ~CPhyeldsController() override;
    void Init(argos::TConfigurationNode& node) override;
    void Reset() override;
    void ControlStep() override;
    void Destroy() override;

    std::string Label;
    argos::CColor Color = argos::CColor::BLACK;

private:
    void Step();
    void SetWheels(argos::CVector2 velocity);
    argos::CCI_DifferentialSteeringActuator* m_wheels = nullptr;
    argos::CCI_LEDsActuator* m_leds = nullptr;
    argos::CCI_RangeAndBearingActuator* m_radio_out = nullptr;
    argos::CCI_RangeAndBearingSensor* m_radio_in = nullptr;
    argos::CCI_PositioningSensor* m_compass = nullptr;
    argos::CCI_FootBotProximitySensor* m_proximity = nullptr;
    _object* m_device = nullptr;
    std::string m_program;
    std::string m_paths = "compact";
    argos::UInt32 m_uid = 0;
    argos::SInt64 m_source = -1;
    argos::Real m_max_speed = 0.1;
    bool m_trace = false;
};
