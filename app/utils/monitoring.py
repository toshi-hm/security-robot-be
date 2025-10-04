class MetricsCollector:
  def record(self, name: str, value: float) -> None:
    print(f'METRIC {name}={value}')


metrics = MetricsCollector()
