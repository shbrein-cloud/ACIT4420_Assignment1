"""Smart Fitness Session Analyzer - entry point.

Usage (from the repository root):
    python3 main.py                              # run all built-in scenarios
    python3 main.py --scenario recovery          # only one scenario
    python3 main.py --generate high_activity --seed 5 --windows 20
    python3 main.py --scenario resting --json    # print the result dictionary
"""

import argparse
import json

from data_generator import available_scenarios, generate_fitness_data
from fitness_analyzer import Session, SessionAnalyzer, format_overview, format_report
from sample_data import get_all_scenarios


def analyze_scenario(analyzer, scenario):
    session = Session.from_raw_data(scenario["name"], scenario["profile"],
                                    scenario["observations"])
    return analyzer.analyze(session)


def print_result(result, title, as_json):
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result, title))
    print()


def parse_arguments():
    parser = argparse.ArgumentParser(description="Smart Fitness Session Analyzer")
    parser.add_argument("--scenario", help="run only the built-in scenario with this name")
    parser.add_argument("--generate", choices=available_scenarios(),
                        help="analyze a newly generated session of this type")
    parser.add_argument("--seed", type=int, default=None, help="seed for --generate")
    parser.add_argument("--windows", type=int, default=12, help="windows for --generate")
    parser.add_argument("--json", action="store_true",
                        help="print the result dictionary as JSON")
    return parser.parse_args()


def main():
    args = parse_arguments()
    analyzer = SessionAnalyzer()

    if args.generate:
        profile, observations = generate_fitness_data(
            "P100", args.generate, seed=args.seed, number_of_windows=args.windows)
        scenario = {"name": "generated_" + args.generate, "profile": profile,
                    "observations": observations}
        print_result(analyze_scenario(analyzer, scenario),
                     "Generated session: " + args.generate, args.json)
        return

    scenarios = get_all_scenarios()
    if args.scenario:
        scenarios = [s for s in scenarios if s["name"] == args.scenario]
        if not scenarios:
            names = ", ".join(s["name"] for s in get_all_scenarios())
            raise SystemExit("Unknown scenario. Choose from: " + names)

    rows = []
    for scenario in scenarios:
        result = analyze_scenario(analyzer, scenario)
        title = "Scenario: {} - {}".format(scenario["name"], scenario["description"])
        print_result(result, title, args.json)
        rows.append({"name": scenario["name"], "expected": scenario["expected"],
                     "result": result})

    if not args.json:
        print("OVERVIEW")
        print(format_overview(rows))


if __name__ == "__main__":
    main()
