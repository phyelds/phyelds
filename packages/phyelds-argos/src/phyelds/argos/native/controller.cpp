#include <cmath>
#include <algorithm>
#include <limits>
#include <regex>
#include "controller.hpp"
#include "python.hpp"
#include <argos3/core/simulator/simulator.h>
#include <argos3/core/simulator/space/space.h>
#include <argos3/core/utility/logging/argos_log.h>

using namespace argos;
using namespace phyelds_argos;

CPhyeldsController::~CPhyeldsController() {
    if (m_device && Py_IsInitialized()) {
        Gil gil;
        Py_DECREF(m_device);
    }
    // The interpreter belongs to the process, never to an individual robot.
}

void CPhyeldsController::Init(TConfigurationNode& node) {
    try {
        GetNodeAttribute(node, "program", m_program);
        GetNodeAttributeOrDefault(node, "source", m_source, m_source);
        GetNodeAttributeOrDefault(node, "max_speed", m_max_speed, m_max_speed);
        GetNodeAttributeOrDefault(node, "paths", m_paths, m_paths);
        GetNodeAttributeOrDefault(node, "gps", m_gps, m_gps);
        GetNodeAttributeOrDefault(node, "trace", m_trace, m_trace);
        if (!std::isfinite(m_max_speed) || m_max_speed < 0)
            throw std::runtime_error("max_speed must be finite and nonnegative");
        if (m_paths != "compact" && m_paths != "debug")
            throw std::runtime_error("paths must be compact or debug");
        std::smatch match;
        auto id = GetId();
        if (!std::regex_match(id, match, std::regex(".*?([0-9]+)$")))
            throw std::runtime_error("robot IDs must end in a unique integer (e.g. fb0)");
        auto uid = std::stoull(match[1].str());
        if (uid > std::numeric_limits<UInt32>::max()) throw std::runtime_error("robot UID exceeds u32");
        m_uid = static_cast<UInt32>(uid);
        m_devices = FindDevices(*this);
        InitializePython();
        Reset();
    } catch (std::exception& error) {
        THROW_ARGOSEXCEPTION_NESTED(GetId() << " initializing " << m_program, error);
    }
}

void CPhyeldsController::Reset() {
    try {
        Gil gil;
        auto separator = m_program.find(':');
        if (separator == std::string::npos || separator == 0 || separator + 1 == m_program.size())
            throw std::runtime_error("program must be module:function");
        auto module = Checked(PyImport_ImportModule(m_program.substr(0, separator).c_str()));
        auto program = Checked(PyObject_GetAttrString(module.get(), m_program.substr(separator + 1).c_str()));
        if (!PyCallable_Check(program.get())) throw std::runtime_error("program is not callable");
        auto runtime = Checked(PyImport_ImportModule("phyelds.vm.device"));
        auto device = Checked(PyObject_GetAttrString(runtime.get(), "Device"));
        auto args = Checked(Py_BuildValue("(IO)", m_uid, program.get()));
        auto kwargs = Checked(Py_BuildValue("{s:s}", "paths", m_paths.c_str()));
        auto replacement = Checked(PyObject_Call(device.get(), args.get(), kwargs.get()));
        Py_XDECREF(m_device);
        m_device = replacement.release();
        Label.clear();
        Color = CColor::BLACK;
        if (m_devices.Drive) m_devices.Drive(CVector3::ZERO);
        if (m_devices.Light) m_devices.Light(Color);
        m_devices.Send(CByteArray());
    } catch (std::exception& error) {
        THROW_ARGOSEXCEPTION_NESTED(GetId() << " resetting " << m_program, error);
    }
}

void CPhyeldsController::ControlStep() {
    try {
        Gil gil;
        Step();
    } catch (std::exception& error) {
        THROW_ARGOSEXCEPTION_NESTED(GetId() << " executing " << m_program, error);
    }
}

void CPhyeldsController::Step() {
    auto const& pose = m_devices.Positioning->GetReading();
    CRadians yaw, pitch, roll;
    pose.Orientation.ToEulerAngles(yaw, pitch, roll);
    auto ranges = Checked(PyDict_New());
    auto vectors = Checked(PyDict_New());
    for (auto& heard : m_devices.Receive()) {
        CByteArray& data = heard.Data;
        if (data.Size() < 6) continue;
        UInt32 sender;
        UInt16 length;
        data >> sender >> length;
        if (!length || length > data.Size() || sender == m_uid) continue;
        auto received = Checked(PyObject_CallMethod(m_device, "receive", "Iy#", sender,
            reinterpret_cast<char const*>(data.ToCArray()), static_cast<Py_ssize_t>(length)));
        if (!heard.Offset) continue;
        CVector3 offset = heard.Offset->Rotate(pose.Orientation);
        auto key = Checked(PyLong_FromUnsignedLong(sender));
        auto distance = Checked(PyFloat_FromDouble(offset.Length()));
        auto vector = Checked(Py_BuildValue("(ddd)", offset.GetX(), offset.GetY(), offset.GetZ()));
        Check(PyDict_SetItem(ranges.get(), key.get(), distance.get()));
        Check(PyDict_SetItem(vectors.get(), key.get(), vector.get()));
    }
    auto sensors = Checked(PyDict_New());
    Real time = CSimulator::GetInstance().GetSpace().GetSimulationClock()
        * CPhysicsEngine::GetSimulationClockTick();
    Put(sensors.get(), "time", Checked(PyFloat_FromDouble(time)));
    Put(sensors.get(), "source", Checked(PyBool_FromLong(m_source == m_uid)));
    Put(sensors.get(), "heading", Checked(Py_BuildValue("(ddd)", Cos(yaw), Sin(yaw), 0.0)));
    if (m_devices.Obstacle) {
        CVector2 obstacle = m_devices.Obstacle().Rotate(yaw);
        Put(sensors.get(), "obstacle", Checked(Py_BuildValue("(ddd)", obstacle.GetX(), obstacle.GetY(), 0.0)));
    }
    if (m_devices.Measures) {
        Put(sensors.get(), "neighbors_distances", std::move(ranges));
        Put(sensors.get(), "neighbors_vectors", std::move(vectors));
    }
    if (m_gps) {
        auto const& position = pose.Position;
        Put(sensors.get(), "position",
            Checked(Py_BuildValue("(ddd)", position.GetX(), position.GetY(), position.GetZ())));
    }
    auto payload = Checked(PyObject_CallMethod(m_device, "run_round", "O", sensors.get()));
    if (!PyBytes_Check(payload.get())) throw std::runtime_error("Device.run_round must return bytes");
    auto length = static_cast<size_t>(PyBytes_Size(payload.get()));
    if (length > std::numeric_limits<UInt16>::max())
        throw std::runtime_error("payload of " + std::to_string(length) + " bytes exceeds the 16-bit frame length");
    CByteArray data;
    data << m_uid << static_cast<UInt16>(length);
    data.AddBuffer(reinterpret_cast<UInt8 const*>(PyBytes_AsString(payload.get())), length);
    m_devices.Send(data);

    auto outputs = Checked(PyObject_GetAttrString(m_device, "outputs"));
    Label.clear();
    if (auto label = PyDict_GetItemString(outputs.get(), "label")) {
        auto text = Checked(PyObject_Str(label));
        auto utf8 = PyUnicode_AsUTF8(text.get());
        if (!utf8) Checked(nullptr);
        Label = utf8;
    }
    Color = CColor::BLACK;
    if (auto led = PyDict_GetItemString(outputs.get(), "led")) {
        auto channels = Checked(PySequence_Fast(led, "led must be an RGB iterable"));
        if (PySequence_Fast_GET_SIZE(channels.get()) != 3) throw std::runtime_error("led must have three channels");
        UInt8 rgb[3];
        for (size_t index = 0; index < 3; ++index) {
            double value = Number(PySequence_Fast_GET_ITEM(channels.get(), index));
            if (value < 0 || value > 255) throw std::runtime_error("led channels must be in [0,255]");
            rgb[index] = static_cast<UInt8>(value);
        }
        Color = CColor(rgb[0], rgb[1], rgb[2]);
    }
    if (m_devices.Light) m_devices.Light(Color);
    CVector3 velocity;
    if (auto value = PyDict_GetItemString(outputs.get(), "velocity")) {
        auto components = Checked(PySequence_Fast(value, "velocity must be an iterable"));
        auto size = PySequence_Fast_GET_SIZE(components.get());
        if (size != 2 && size != 3) throw std::runtime_error("velocity must have two or three components");
        velocity.Set(Number(PySequence_Fast_GET_ITEM(components.get(), 0)),
                     Number(PySequence_Fast_GET_ITEM(components.get(), 1)),
                     size == 3 ? Number(PySequence_Fast_GET_ITEM(components.get(), 2)) : 0);
        if (velocity.Length() > m_max_speed) velocity *= m_max_speed / velocity.Length();
    }
    if (m_devices.Drive) m_devices.Drive(velocity);
    if (m_trace) LOG << GetId() << " round: " << Label << std::endl;
}

void CPhyeldsController::Destroy() {
    LOG << GetId() << " final: " << Label << std::endl;
    LOG.Flush();
}

REGISTER_CONTROLLER(CPhyeldsController, "phyelds_controller")
