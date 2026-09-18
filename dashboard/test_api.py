import urllib.request
import json
import sys

base_url = 'http://localhost:8000'

try:
    # 1. Test Status
    req = urllib.request.urlopen(f'{base_url}/api/status')
    status_data = json.loads(req.read().decode())
    print('1. STATUS ENDPOINT: OK (Status:', status_data.get('status'), '| Ovens:', status_data.get('oven_types'), ')')

    # 2. Test Presets
    req = urllib.request.urlopen(f'{base_url}/api/presets')
    presets = json.loads(req.read().decode())
    print(f'2. PRESETS ENDPOINT: OK ({len(presets)} presets: {list(presets.keys())})')

    # 3. Test Prediction with Normal ED
    normal_preset = presets['normal_ed']
    req_data = json.dumps(normal_preset['data']).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    req = urllib.request.Request(f'{base_url}/api/predict', data=req_data, headers=headers)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        audit = res['quality_audit']
        print('3. PREDICT (Normal): OK -> Verdict:', res['verdict'], 
              '| Final Status:', audit['final_status'],
              '| CQI:', audit['cure_quality_index_pct'], '%',
              '| Cross-Body Spread:', audit['cross_body_spread_C'], '°C',
              '| Sensors returned in time_series:', len(res['time_series']) - 1)

    # 4. Test Prediction with Failure preset (burner trip)
    trip_preset = presets['burner_trip']
    req_data = json.dumps(trip_preset['data']).encode('utf-8')
    req = urllib.request.Request(f'{base_url}/api/predict', data=req_data, headers=headers)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        audit = res['quality_audit']
        print('4. PREDICT (Failure Mode): OK -> Verdict:', res['verdict'], 
              '| Final Status:', audit['final_status'],
              '| CQI:', audit['cure_quality_index_pct'], '%',
              '| Diagnosed Failure:', res['failure_mode'],
              '| Suspect Subsystem:', res['primary_subsystem'])

    # 5. Test Standard Curve
    req = urllib.request.urlopen(f'{base_url}/api/standard-curve/ED/CC21')
    std_data = json.loads(req.read().decode())
    print('5. STANDARD CURVE: OK -> Samples:', len(std_data['standard_temp_C']), 
          '| Guard bands upper/lower:', len(std_data['upper_limit_C']), len(std_data['lower_limit_C']))

    # 6. Test Export Certificate
    req = urllib.request.Request(f'{base_url}/api/export-certificate', data=req_data, headers=headers)
    with urllib.request.urlopen(req) as resp:
        html_content = resp.read().decode()
        print('6. CERTIFICATE EXPORT: OK -> HTML Certificate length:', len(html_content), 'chars')

    print('\n======================================================')
    print('ALL PHASE 4 BACKEND & REST API TESTS PASSED SUCCESSFULLY!')
    print('======================================================')
except Exception as e:
    import traceback
    traceback.print_exc()
    print('Error:', e)
    sys.exit(1)
