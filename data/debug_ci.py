import numpy as np, random, sys
np.random.seed(42); random.seed(42)
sys.path.insert(0,'.')
from generate_sample_data import *

spec = OVEN_SPECS['ED']
sensor_summaries = []
for sensor in SENSORS:
    profile = generate_temperature_profile(spec, sensor, 'CC21', None)
    cv = calculate_critical_values(profile, spec)
    sensor_summaries.append({"sensor": sensor["name"], **cv})

print("Sensor CI values:")
for s in sensor_summaries:
    print("  %s: CI=%.1f  t_above=%.2f  peak=%.1f" % (s["sensor"], s["cure_index"], s["time_above_cure_min"], s["peak_temp_C"]))

result, reasons = judge_result(sensor_summaries, spec)
print("Result:", result)
for r in reasons:
    print("  FAIL:", r)
