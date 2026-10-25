#include <argos3/core/control_interface/ci_controller.h>
#include <argos3/plugins/robots/generic/control_interface/ci_range_and_bearing_actuator.h>

class CBadSender : public argos::CCI_Controller {
public:
    void Init(argos::TConfigurationNode&) override {
        m_radio = GetActuator<argos::CCI_RangeAndBearingActuator>("range_and_bearing");
    }
    void ControlStep() override {
        argos::CByteArray data;
        if (m_radio->GetSize() >= 6) data << argos::UInt32(99) << argos::UInt16(5000);
        data.Resize(m_radio->GetSize());
        m_radio->SetData(data);
    }
private:
    argos::CCI_RangeAndBearingActuator* m_radio;
};
REGISTER_CONTROLLER(CBadSender, "bad_sender")
