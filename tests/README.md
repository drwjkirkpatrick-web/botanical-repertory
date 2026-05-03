# Botanical Repertory Test Suite

This directory contains comprehensive tests for the Botanical Medicine Repertory project.

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration and fixtures
├── test_models.py       # Data model tests
├── test_heuristics.py   # Extraction heuristics tests
├── test_search.py       # Search functionality tests
├── test_database.py     # Database operation tests
└── test_integration.py  # Integration tests
```

## Running Tests

### Run all tests:
```bash
cd ~/.hermes/projects/botanical_repertory
python -m pytest tests/ -v
```

### Run specific test file:
```bash
python -m pytest tests/test_models.py -v
```

### Run with coverage:
```bash
python -m pytest tests/ --cov=src --cov=search --cov=ingestion -v
```

### Run only unit tests (skip integration):
```bash
python -m pytest tests/ -v -m "not integration"
```

### Run only integration tests:
```bash
python -m pytest tests/ -v -m "integration"
```

## Test Categories

### Unit Tests (test_*.py)
- Fast, isolated tests
- No database required (uses fixtures/mocks)
- Test individual components

### Integration Tests (test_integration.py)
- Require database
- Test full workflows
- Marked with `@pytest.mark.integration`

## Writing New Tests

### Basic test structure:
```python
def test_something():
    """Test description."""
    # Arrange
    input_data = "test"
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    assert result == expected_value
```

### Using fixtures:
```python
def test_with_database(temp_db):
    """Test using temporary database."""
    # temp_db is automatically created and cleaned up
    stats = temp_db.get_stats()
    assert stats["botanicals"] == 0
```

### Marking slow tests:
```python
@pytest.mark.slow
def test_slow_operation():
    """A slow test that might be skipped in CI."""
    pass
```

## Coverage Goals

- Models: 100%
- Database: 90%
- Heuristics: 85%
- Search: 80%
- Integration: 70%

## Continuous Integration

Tests are designed to run in CI environments. Tests that require
external resources are marked and skipped automatically when
credentials are not available.
