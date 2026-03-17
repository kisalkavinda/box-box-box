import json
import subprocess
import os
import glob
import sys
import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Run race simulator against test cases.')
    parser.add_argument(
        '--test',
        help='Run a specific test by number (e.g. 43), file name (test_043.json), or glob (test_04*.json).',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=20,
        help='Per-test subprocess timeout in seconds (default: 20).',
    )
    return parser.parse_args()

def main():
    args = parse_args()
    root = Path(__file__).resolve().parent

    if args.test:
        if args.test.isdigit():
            test_pattern = f"test_{int(args.test):03d}.json"
        elif args.test.startswith('test_') and args.test.endswith('.json'):
            test_pattern = args.test
        else:
            test_pattern = args.test
        test_inputs = sorted(glob.glob(str(root / 'data/test_cases/inputs' / test_pattern)))
    else:
        test_inputs = sorted(glob.glob(str(root / 'data/test_cases/inputs/test_*.json')))

    expected_outputs = root / 'data/test_cases/expected_outputs'
    simulator = root / 'solution/race_simulator.py'

    if not test_inputs:
        print('No matching test inputs found.')
        return
    
    passed = 0
    total = len(test_inputs)
    
    print(f"Running {total} tests...")
    
    completed = 0

    try:
        for test_file in test_inputs:
            test_name = os.path.basename(test_file)
            expected_file = expected_outputs / test_name

            # Run solution
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    process = subprocess.run(
                        [sys.executable, str(simulator)],
                        stdin=f,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=str(root),
                        timeout=args.timeout,
                        check=False,
                    )
                    stdout, stderr = process.stdout, process.stderr

                if process.returncode != 0:
                    print(f"x {test_name}: Execution Error")
                    if stderr:
                        print(f"  {stderr.strip()}")
                    completed += 1
                    continue

                prediction = json.loads(stdout)

                with open(expected_file, 'r', encoding='utf-8') as f:
                    expected = json.load(f)

                if 'finishing_positions' not in prediction:
                    print(f"x {test_name}: Missing 'finishing_positions' in simulator output")
                    completed += 1
                    continue

                if prediction['finishing_positions'] == expected['finishing_positions']:
                    passed += 1
                    # print(f"✓ {test_name}")
                else:
                    matches = sum(1 for a, b in zip(expected['finishing_positions'], prediction['finishing_positions']) if a == b)
                    print(f"x {test_name}: Incorrect Prediction ({matches}/20 matches)")
                completed += 1
            except subprocess.TimeoutExpired:
                print(f"x {test_name}: Timeout after {args.timeout}s")
                completed += 1
            except Exception as e:
                print(f"x {test_name}: {str(e)}")
                completed += 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    print(f"Completed: {completed}/{total}")
    print(f"Final Result: {passed}/{total} ({100*passed/total:.1f}%)")

if __name__ == '__main__':
    main()
