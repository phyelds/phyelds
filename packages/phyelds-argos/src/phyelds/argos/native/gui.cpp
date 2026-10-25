#include <algorithm>
#include <argos3/core/simulator/entity/composable_entity.h>
#include <argos3/core/simulator/entity/controllable_entity.h>
#include <argos3/core/simulator/entity/embodied_entity.h>
#include <argos3/core/simulator/simulator.h>
#include <argos3/core/simulator/space/space.h>
#include <argos3/plugins/simulator/visualizations/qt-opengl/qtopengl_user_functions.h>
#include "controller.hpp"

// Under every robot a phyelds controller drives, whatever its type, a halo of its LED
// colour, and its label above it.
class CPhyeldsQTUserFunctions : public argos::CQTOpenGLUserFunctions {
public:
    void DrawInWorld() override {
        QFont font;
        font.setPixelSize(12);
        for (auto& [id, entity] : argos::CSimulator::GetInstance().GetSpace().GetEntitiesByType("controller")) {
            auto& controllable = *argos::any_cast<argos::CControllableEntity*>(entity);
            auto* controller = dynamic_cast<CPhyeldsController*>(&controllable.GetController());
            auto& robot = controllable.GetParent();
            if (!controller || !robot.HasComponent("body")) continue;
            auto const& box = robot.GetComponent<argos::CEmbodiedEntity>("body").GetBoundingBox();
            argos::CVector3 base = (box.MinCorner + box.MaxCorner) * 0.5;
            base.SetZ(box.MinCorner.GetZ());
            argos::Real radius = 0.75 * std::max(box.MaxCorner.GetX() - box.MinCorner.GetX(),
                                                 box.MaxCorner.GetY() - box.MinCorner.GetY());
            DrawCylinder(base, argos::CQuaternion(), radius, 0.01, controller->Color);
            DrawText(argos::CVector3(base.GetX(), base.GetY(), box.MaxCorner.GetZ() + 0.05),
                     controller->Label, argos::CColor::BLACK, font);
        }
    }
};
REGISTER_QTOPENGL_USER_FUNCTIONS(CPhyeldsQTUserFunctions, "phyelds_qtuser_functions")
