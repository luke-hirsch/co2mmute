# Traffic Simulation Tests

Comprehensive unit tests for the CO2mmute traffic simulation system.

## Test Coverage

### ✅ Capacity Calculation Tests (`CapacityCalculationTests`)
Tests the improved capacity calculation function that accounts for speed limits and lanes:
- Basic capacity calculation (1 car per km calculation)
- Multi-lane scaling
- Different speed limits
- Short roads and edge cases
- Realistic urban and highway scenarios

**Key Improvements Tested:**
- Old: Simple 1 car per 50m
- New: Dynamic calculation based on speed and lanes

### ✅ BPR Speed Function Tests (`BPRSpeedFunctionTests`)
Tests the Bureau of Public Roads congestion model:
- Free flow conditions (no traffic)
- At capacity performance
- Over-capacity congestion
- Severe congestion scenarios
- Edge cases (zero/negative capacity)

**BPR Formula:** `speed = free_flow_speed / (1 + 0.15 × (volume/capacity)^4)`

### ✅ EdgeState Tests (`EdgeStateTests`)
Tests the core traffic state management:
- Volume calculation (excluding buses on dedicated lanes)
- Total vehicles count (including all buses)
- Speed calculation with congestion
- Dedicated bus lane handling

**Critical Feature:**
- Buses on dedicated lanes don't contribute to traffic congestion
- Traffic speed calculations are accurate

### ✅ Departure Time Generation Tests (`DepartureTimeGenerationTests`)
Tests the randomized departure time generation:
- Correct number of departures
- Non-negative times
- Different tick durations
- Normal distribution behavior
- Zero standard deviation (everyone departs together)

### ✅ Simulation Parameter Loading Tests (`SimulationParameterLoadingTests`)
Tests loading of dynamic simulation parameters from GameSession:
- `people_per_agent` (default: 1000)
- `tick_duration_min` (default: 5)
- `morning_departure_hour` (default: 9)
- `evening_departure_hour` (default: 17)
- `departure_std_dev_min` (default: 10)

**Also Tests:**
- Speed parameters from GameMap
- Fallback values when map is not set

### ✅ PT Line Speed Loading Tests (`PTLineSpeedLoadingTests`)
Tests loading of bus and train speeds from database:
- Bus line custom speeds
- Train line custom speeds
- Proper caching of speeds for performance
- Integration with route segments

### ✅ Bus Traffic Integration Tests (`BusTrafficIntegrationTests`)
Tests the critical feature of bus-traffic interaction:
- **Dedicated bus lane**: Buses don't affect car traffic
- **Regular street**: Buses contribute to congestion
- Volume calculations are correct
- Speed calculations reflect reality

## Running the Tests

### Option 1: Using Django Test Runner (Recommended)
```bash
cd backend
python manage.py test game.tests_simulation --verbosity=2
```

### Option 2: Using pytest
```bash
cd backend
pytest game/tests_simulation.py -v
```

### Option 3: Run Specific Test Class
```bash
python manage.py test game.tests_simulation.CapacityCalculationTests
python manage.py test game.tests_simulation.BPRSpeedFunctionTests
python manage.py test game.tests_simulation.EdgeStateTests
# etc...
```

### Option 4: Run Specific Test Method
```bash
python manage.py test game.tests_simulation.CapacityCalculationTests.test_capacity_basic
```

## Test Statistics

- **Total Test Classes**: 8
- **Total Test Methods**: 32+
- **Coverage Areas**:
  - ✅ Mathematical functions (BPR, capacity)
  - ✅ Data structures (EdgeState)
  - ✅ Model loading (speeds, parameters)
  - ✅ Business logic (bus traffic, congestion)
  - ✅ Edge cases and error handling

## What's Tested

### Core Functions
- `calculate_edge_capacity()` - Realistic capacity modeling
- `bpr_speed()` - Congestion speed calculation
- `generate_departure_times()` - Random departure scheduling

### Data Structures
- `EdgeState` - Traffic state management
  - Volume tracking
  - Bus separation
  - Speed calculation

### Model Integration
- GameSession parameters loading
- GameMap speed settings
- BusLine/TrainLine speeds
- Route segment PT line references

### Key Features
- **Bus dedicated lanes**: Properly separated from car traffic
- **Multi-lane roads**: Capacity scales correctly
- **Speed-based capacity**: Realistic traffic flow
- **Congestion modeling**: BPR function working correctly

## Example Test Output

```
test_capacity_basic (game.tests_simulation.CapacityCalculationTests) ... ok
test_capacity_multiple_lanes (game.tests_simulation.CapacityCalculationTests) ... ok
test_bus_on_dedicated_lane_not_in_volume (game.tests_simulation.BusTrafficIntegrationTests) ... ok
test_bus_on_regular_street_in_volume (game.tests_simulation.BusTrafficIntegrationTests) ... ok

----------------------------------------------------------------------
Ran 32 tests in 0.5s

OK
```

## Adding New Tests

When adding new simulation features, add tests following this pattern:

```python
class YourFeatureTests(TestCase):
    """Tests for your new feature."""

    def setUp(self):
        """Set up test data."""
        # Create necessary models
        pass

    def test_basic_functionality(self):
        """Test basic behavior."""
        # Arrange
        # Act
        # Assert
        pass

    def test_edge_case(self):
        """Test edge cases."""
        pass
```

## Continuous Testing

These tests should be run:
- ✅ Before committing simulation changes
- ✅ In CI/CD pipeline
- ✅ After database migrations
- ✅ When updating models

## Test Data

Tests use Django's test database with:
- Isolated test cases (no data pollution)
- Transaction rollback after each test
- In-memory SQLite for speed

## Known Limitations

- Tests require Django environment (can't run standalone)
- Database required (uses Django ORM)
- Some integration tests need full app context

## Debugging Tests

To debug a specific test:

```python
# Add to your test method
import pdb; pdb.set_trace()

# Or use print statements
print(f"Volume: {edge_state.volume}")
print(f"Speed: {edge_state.get_current_speed()}")
```

Run with verbose output:
```bash
python manage.py test game.tests_simulation.YourTest.your_method --verbosity=3
```

## Future Test Additions

Potential areas for more tests:
- [ ] Full simulation end-to-end test
- [ ] Multi-agent interaction
- [ ] Complex route scenarios
- [ ] Performance/load testing
- [ ] CO2 calculation accuracy
- [ ] Edge case handling (empty maps, etc.)

---

**Created**: 2026-02-08
**Last Updated**: 2026-02-08
**Test Framework**: Django TestCase + pytest
**Coverage**: Core simulation logic, mathematical functions, model integration
