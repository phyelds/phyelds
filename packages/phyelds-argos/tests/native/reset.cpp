#include <argos3/core/simulator/simulator.h>
#include <argos3/core/utility/plugins/dynamic_loading.h>
#include <iostream>
#include <argos3/core/utility/logging/argos_log.h>

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    argos::LOG.DisableColoredOutput();
    argos::LOGERR.DisableColoredOutput();
    try {
        argos::CDynamicLoading::LoadAllLibraries();
        auto& simulator = argos::CSimulator::GetInstance();
        simulator.SetExperimentFileName(argv[1]);
        simulator.LoadExperiment(true);
        simulator.Execute();
        simulator.Reset();
        simulator.Execute();
        simulator.Destroy();
    } catch (std::exception const& error) {
        std::cerr << error.what() << std::endl;
        return 1;
    }
}
