#include <argos3/plugins/robots/foot-bot/simulator/footbot_entity.h>
#include <argos3/plugins/simulator/visualizations/qt-opengl/qtopengl_user_functions.h>
#include "controller.hpp"

class CPhyeldsQTUserFunctions : public argos::CQTOpenGLUserFunctions {
public:
    CPhyeldsQTUserFunctions() {
        RegisterUserFunction<CPhyeldsQTUserFunctions, argos::CFootBotEntity>(&CPhyeldsQTUserFunctions::Draw);
    }
    void Draw(argos::CFootBotEntity& entity) {
        auto* controller = dynamic_cast<CPhyeldsController*>(&entity.GetControllableEntity().GetController());
        if (!controller) return;
        DrawCylinder(argos::CVector3(0, 0, 0), argos::CQuaternion(), 0.14, 0.01, controller->Color);
        QFont font;
        font.setPixelSize(12);
        DrawText(argos::CVector3(0, 0, 0.35), controller->Label, argos::CColor::BLACK, font);
    }
};
REGISTER_QTOPENGL_USER_FUNCTIONS(CPhyeldsQTUserFunctions, "phyelds_qtuser_functions")
