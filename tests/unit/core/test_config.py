"""Unit tests for application configuration and device validation."""

from pydantic import ValidationError
import pytest
import torch

from app.core.config import Settings


class TestSettingsTrainingDevice:
  """Test training device configuration and validation."""

  def test_default_device_is_auto(self):
    """Test that default training device is 'auto'."""
    settings = Settings()
    assert settings.training_device == "auto"

  def test_cpu_device_is_valid(self):
    """Test that 'cpu' is accepted as training device."""
    settings = Settings(training_device="cpu")
    assert settings.training_device == "cpu"

  def test_cuda_device_is_valid_when_available(self):
    """Test that 'cuda' is accepted when CUDA is available."""
    if not torch.cuda.is_available():
      pytest.skip("CUDA not available")
    settings = Settings(training_device="cuda")
    assert settings.training_device == "cuda"

  def test_cuda_device_fails_when_unavailable(self):
    """Test that 'cuda' raises error when CUDA is not available."""
    if torch.cuda.is_available():
      pytest.skip("CUDA is available")
    with pytest.raises(ValidationError, match="CUDA is not available"):
      Settings(training_device="cuda")

  def test_cuda_indexed_device_is_valid_when_available(self):
    """Test that 'cuda:0' is accepted when CUDA device 0 is available."""
    if not torch.cuda.is_available():
      pytest.skip("CUDA not available")
    settings = Settings(training_device="cuda:0")
    assert settings.training_device == "cuda:0"

  def test_cuda_indexed_device_fails_when_out_of_range(self):
    """Test that 'cuda:N' raises error when device N is out of range."""
    if not torch.cuda.is_available():
      pytest.skip("CUDA not available")
    device_count = torch.cuda.device_count()
    invalid_idx = device_count + 10
    with pytest.raises(ValidationError, match="Invalid CUDA device specification"):
      Settings(training_device=f"cuda:{invalid_idx}")

  def test_invalid_device_raises_error(self):
    """Test that invalid device string raises error."""
    with pytest.raises(ValidationError, match="must be 'auto', 'cpu', 'cuda', or 'cuda:N'"):
      Settings(training_device="gpu")

  def test_get_training_device_auto_returns_cuda_when_available(self):
    """Test that get_training_device returns 'cuda' when auto and CUDA available."""
    if not torch.cuda.is_available():
      pytest.skip("CUDA not available")
    settings = Settings(training_device="auto")
    device = settings.get_training_device()
    assert device == "cuda"

  def test_get_training_device_auto_returns_cpu_when_unavailable(self):
    """Test that get_training_device returns 'cpu' when auto and CUDA unavailable."""
    if torch.cuda.is_available():
      pytest.skip("CUDA is available")
    settings = Settings(training_device="auto")
    device = settings.get_training_device()
    assert device == "cpu"

  def test_get_training_device_returns_configured_value(self):
    """Test that get_training_device returns configured non-auto value."""
    settings = Settings(training_device="cpu")
    device = settings.get_training_device()
    assert device == "cpu"

  def test_device_string_is_normalized_to_lowercase(self):
    """Test that device string is normalized to lowercase."""
    settings = Settings(training_device="CPU")
    assert settings.training_device == "cpu"

  def test_device_string_is_stripped(self):
    """Test that device string whitespace is stripped."""
    settings = Settings(training_device="  cpu  ")
    assert settings.training_device == "cpu"
