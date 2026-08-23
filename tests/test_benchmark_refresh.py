from app.data.benchmark_refresh import BENCHMARKS

def test_briefing_benchmarks_are_broad_and_non_executable():
    assert BENCHMARKS==("SPY","QQQ","IWM")
