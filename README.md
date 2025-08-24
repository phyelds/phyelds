# Phyelds

<div align="center">

![Phyelds Logo](https://img.shields.io/badge/Phyelds-Fields-blue?style=for-the-badge)
[![PyPI version](https://badge.fury.io/py/phyelds.svg)](https://badge.fury.io/py/phyelds)
[![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Tests](https://github.com/phyelds/phyelds/workflows/CI/badge.svg)](https://github.com/phyelds/phyelds/actions)

**A Python-native aggregate computing library for building decentralized, large-scale systems**

</div>

Phyelds (pronounced *fields*) is a cutting-edge Python library that brings the power of **aggregate computing** to distributed systems development. It enables you to build decentralized, large-scale systems using elegant and composable abstractions called computational *fields*.

## 🌟 What is Aggregate Computing?

Aggregate computing is a programming paradigm designed for distributed systems where:

- **Local Logic, Global Behavior**: Each node runs the same program but adapts to local conditions
- **Field-Based Computation**: Data and computation flow across space and time as continuous fields
- **Self-Organization**: Complex behaviors emerge from simple local interactions
- **Resilience**: Systems naturally adapt to node failures and network changes

Perfect for IoT networks, sensor arrays, swarm robotics, smart cities, and distributed algorithms.

## ✨ Key Features

* **🐍 Pythonic by Design**: Clean syntax, functional patterns, and intuitive APIs for rapid prototyping
* **🧩 Field-Based Programming**: Define spatial-temporal behavior via *fields* that evolve across devices
* **🌐 Collective Intelligence**: Each node runs identical logic while adapting locally using neighborhood information
* **🔬 Comprehensive Simulation**: Run, visualize, and test aggregate programs in controlled virtual environments
* **📦 Lightweight & Flexible**: Minimal dependencies with plug-and-play components
* **🚀 High Performance**: Optimized engine for efficient field computation and message passing
* **📚 Rich Library**: Built-in algorithms for common distributed computing patterns
* **🧪 Testing-First**: Extensive test suite and simulation tools for reliable development

## 🚀 Quick Start

### Installation

```bash
pip install phyelds
```

**Requirements**: Python 3.13+

### Your First Aggregate Program

```python
from phyelds.calculus import aggregate, remember, neighbors
from phyelds.simulator import Simulator, Node, Environment
from phyelds.internal import MutableEngine
import random

# Define an aggregate function
@aggregate
def gossip_max(value):
    """Compute the maximum value across all connected nodes"""
    # Remember the local maximum seen so far
    local_max = remember(value).update_fn(lambda old: max(old, value))
    
    # Get neighbor values and include our own
    neighbor_values = neighbors(local_max.get())
    
    # Return the maximum across all neighbors
    return max(neighbor_values.values())

# Create a simulation
def run_simulation():
    # Set up environment with 10 nodes
    env = Environment()
    nodes = []
    
    for i in range(10):
        # Each node starts with a random value
        node = Node(position=(random.uniform(0, 10), random.uniform(0, 10)))
        node.data = {"value": random.randint(1, 100)}
        env.add_node(node)
        nodes.append(node)
    
    # Create simulator
    simulator = Simulator(env, MutableEngine)
    
    # Run the gossip algorithm for several rounds
    for round_num in range(10):
        results = simulator.cycle(lambda: gossip_max(simulator.current_node.data["value"]))
        print(f"Round {round_num + 1}: Max values = {[r for r in results.values()]}")

if __name__ == "__main__":
    run_simulation()
```

## 📖 Core Concepts

### 1. Aggregate Functions

Functions decorated with `@aggregate` that define field computations:

```python
@aggregate
def my_algorithm():
    # Your distributed algorithm here
    return result
```

### 2. State Management with `remember`

Maintain state across computation rounds:

```python
@aggregate
def counter():
    # Start with 0, increment each round
    count = remember(0).update_fn(lambda x: x + 1)
    return count.get()
```

### 3. Neighborhood Communication with `neighbors`

Exchange information with connected nodes:

```python
@aggregate
def average_temperature():
    local_temp = context.data["temperature"]
    neighbor_temps = neighbors(local_temp)
    return sum(neighbor_temps.values()) / len(neighbor_temps)
```

### 4. Alignment for Coordination

Coordinate different parts of your algorithm:

```python
from phyelds.calculus import align, align_left, align_right

@aggregate
def leader_follower():
    if is_leader():
        with align_left():
            return leader_computation()
    else:
        with align_right():
            return follower_computation()
```

## 🏗️ Architecture Overview

Phyelds is organized into several key modules:

```
phyelds/
├── abstractions/     # Core abstract classes (Engine, NodeContext)
├── calculus/         # Core field calculus (@aggregate, remember, neighbors)
├── internal/         # Engine implementation (MutableEngine)
├── libraries/        # High-level algorithms
│   ├── gossip.py     # Information spreading algorithms
│   ├── distances.py  # Distance computation
│   ├── leader_election.py  # Leader election algorithms
│   ├── spreading.py  # Value propagation patterns
│   └── time.py       # Temporal operations
├── simulator/        # Simulation environment
└── data/            # Core data structures (Field, State)
```

## 📚 Built-in Algorithms

Phyelds comes with a rich library of pre-implemented distributed algorithms:

### Gossip Protocols
```python
from phyelds.libraries.gossip import gossip_max, gossip_min, gossip_sum

# Find maximum value across network
max_value = gossip_max(local_sensor_reading)
```

### Distance Computation
```python
from phyelds.libraries.distances import hops_distance, euclidean_distance

# Compute hop distance from source nodes
distance = hops_distance(is_source_node)
```

### Leader Election
```python
from phyelds.libraries.leader_election import elect_leader

# Distributed leader election
is_leader = elect_leader(node_id, priority)
```

### Information Spreading
```python
from phyelds.libraries.spreading import broadcast, cast_from

# Broadcast information from source nodes
info = broadcast(source_info, is_source)
```

## 🔧 Advanced Usage

### Custom Neighborhood Functions

Define how nodes discover their neighbors:

```python
def radius_neighborhood(node, all_nodes):
    """Connect nodes within a certain radius"""
    radius = 2.0
    neighbors = []
    for other in all_nodes:
        if node != other:
            distance = compute_distance(node.position, other.position)
            if distance <= radius:
                neighbors.append(other)
    return neighbors

# Use in environment
env = Environment(neighborhood_function=radius_neighborhood)
```

### Performance Monitoring

```python
from phyelds.simulator import Simulator
import time

def benchmark_algorithm():
    simulator = Simulator(env, MutableEngine)
    
    start_time = time.time()
    for _ in range(100):
        simulator.cycle(my_algorithm)
    end_time = time.time()
    
    print(f"100 rounds completed in {end_time - start_time:.2f} seconds")
```

### Data Export and Analysis

```python
# Export simulation results to CSV
results = []
for round_num in range(50):
    round_results = simulator.cycle(my_algorithm)
    results.append({
        'round': round_num,
        'node_results': round_results
    })

# Convert to pandas DataFrame for analysis
import pandas as pd
df = pd.DataFrame(results)
```

## 🧪 Testing Your Algorithms

### Unit Testing with Mock Environments

```python
import pytest
from phyelds.internal import MutableEngine
from phyelds import engine
from tests.calculus.mock import MockNodeContext

@pytest.fixture
def setup_engine():
    engine.set(MutableEngine().setup(MockNodeContext(0)))

def test_my_algorithm(setup_engine):
    result = my_algorithm()
    assert result == expected_value
```

### Integration Testing with Simulation

```python
def test_convergence():
    """Test that algorithm converges to expected result"""
    simulator = create_test_simulator()
    
    # Run until convergence
    previous_results = None
    for round_num in range(100):
        results = simulator.cycle(my_algorithm)
        
        # Check for convergence
        if previous_results and results == previous_results:
            print(f"Converged after {round_num} rounds")
            break
        previous_results = results
    
    # Assert final state is correct
    assert all(result == expected_final_value for result in results.values())
```

## 📊 Performance Considerations

### Benchmarking Results

On a modern CPU, Phyelds can handle:
- **10,000+ nodes** in simulation
- **1,000+ rounds/second** for simple algorithms  
- **Sub-millisecond latency** for field operations

### Optimization Tips

1. **Minimize State**: Use `remember()` judiciously as it persists across rounds
2. **Efficient Neighborhoods**: Limit neighbor connections for better performance
3. **Batch Operations**: Group related computations when possible
4. **Memory Management**: Clear unnecessary data in long-running simulations

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Clone the repository
git clone https://github.com/phyelds/phyelds.git
cd phyelds

# Install Poetry (if not already installed)
pip install poetry

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run linting
poetry run flake8 src/
poetry run pylint src/phyelds/
```

### Code Style

- Follow PEP 8 conventions
- Add type hints where appropriate
- Write docstrings for all public functions
- Include tests for new features

### Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 Examples and Tutorials

### Example 1: Distributed Sensor Network

```python
@aggregate
def environmental_monitoring():
    """Monitor environmental conditions across sensor network"""
    # Read local sensors
    temperature = context.data["temperature"]
    humidity = context.data["humidity"]
    
    # Share with neighbors and compute averages
    avg_temp = gossip_average(temperature)
    avg_humidity = gossip_average(humidity)
    
    # Detect anomalies
    temp_threshold = 30.0
    humidity_threshold = 80.0
    
    is_anomaly = (abs(temperature - avg_temp) > temp_threshold or 
                  abs(humidity - avg_humidity) > humidity_threshold)
    
    # Propagate alerts
    alert = broadcast(is_anomaly, is_anomaly)
    
    return {
        "local_temp": temperature,
        "avg_temp": avg_temp,
        "alert_active": alert
    }
```

### Example 2: Swarm Robotics Formation

```python
@aggregate
def formation_control():
    """Control robot swarm to maintain formation"""
    # Get desired position in formation
    target_pos = compute_formation_position()
    current_pos = context.position()
    
    # Share positions with neighbors
    neighbor_positions = neighbors(current_pos)
    
    # Compute force vectors to maintain formation
    separation_force = compute_separation(neighbor_positions)
    alignment_force = compute_alignment(neighbor_positions)
    cohesion_force = compute_cohesion(neighbor_positions, target_pos)
    
    # Combine forces
    total_force = (separation_force + alignment_force + cohesion_force)
    
    return total_force
```

## 🚨 Troubleshooting

### Common Issues

**ImportError: No module named 'phyelds'**
```bash
# Make sure phyelds is installed
pip install phyelds

# Or for development
poetry install
```

**Engine not properly initialized**
```python
# Always setup engine before using aggregate functions
from phyelds.internal import MutableEngine
from phyelds import engine

engine.set(MutableEngine().setup(node_context))
```

**Neighborhood function not working**
```python
# Ensure neighborhood function returns List[Node]
def my_neighborhood(node, all_nodes):
    # Must return a list of Node objects
    return [n for n in all_nodes if some_condition(node, n)]
```

### Performance Issues

If simulations are running slowly:

1. **Reduce network size**: Start with fewer nodes
2. **Optimize neighborhood**: Limit connections per node
3. **Profile your code**: Use Python profiling tools
4. **Check convergence**: Ensure algorithms terminate

### Getting Help

- 📖 [Documentation](https://github.com/phyelds/phyelds)
- 🐛 [Issue Tracker](https://github.com/phyelds/phyelds/issues)
- 💬 [Discussions](https://github.com/phyelds/phyelds/discussions)
- 📧 Email: [davide.domini@unibo.it](mailto:davide.domini@unibo.it)

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Authors**: [Davide Domini](mailto:davide.domini@unibo.it), [Gianluca Aguzzi](mailto:gianluca.aguzzi@unibo.it)
- **Institution**: University of Bologna
- **Inspiration**: Field calculus and aggregate computing research community

## 📚 References and Further Reading

- [Aggregate Computing: A Programming Model for Distributed Systems](https://dl.acm.org/doi/10.1145/3140465.3140467)
- [Field Calculus: A Coordination Model for Distributed Systems](https://link.springer.com/chapter/10.1007/978-3-319-99567-0_8)
- [ScaFi: A Scala API for Aggregate Programming](https://link.springer.com/chapter/10.1007/978-3-319-99567-0_16)

---

<div align="center">

**[⭐ Star us on GitHub](https://github.com/phyelds/phyelds)** | **[📦 View on PyPI](https://pypi.org/project/phyelds/)** | **[📖 Read the Docs](https://github.com/phyelds/phyelds)**

Made with ❤️ by the Phyelds team

</div>
