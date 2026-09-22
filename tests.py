"""Automated tests. Run with:  python3 tests.py   (or python3 -m unittest tests)"""

import unittest

from data_generator import available_scenarios, generate_fitness_data
from fitness_analyzer import Observation, Participant, Session, SessionAnalyzer, format_report
from fitness_analyzer.calculations import (check_range, compare_with_reference, is_number,
                                           linear_slope, split_start_and_end, summarize)
from fitness_analyzer.rules import ClassificationRule, RecoveryRule
from sample_data import get_all_scenarios

EXPECTED_LABELS = {
    "resting": "resting",
    "moderate_activity": "moderate activity",
    "high_activity": "high activity",
    "recovery": "recovering",
    "poor_quality": "insufficient data",
}

PROFILE = {"participant_id": "T1", "baseline_heart_rate": 70,
           "baseline_skin_response": 1.5, "baseline_temperature": 32.5}


def make_observation(timestamp=0, **changes):
    data = {"timestamp": timestamp, "heart_rate": 80, "skin_response": 1.6,
            "temperature": 32.6, "activity_level": 0.2, "signal_quality": 0.9}
    data.update(changes)
    return Observation.from_dict(data)


class CalculationTests(unittest.TestCase):
    def test_summarize(self):
        result = summarize([2, 4, 6])
        self.assertEqual(result["mean"], 4)
        self.assertEqual((result["min"], result["max"], result["count"]), (2, 6, 3))

    def test_summarize_empty(self):
        self.assertIsNone(summarize([])["mean"])

    def test_check_range(self):
        self.assertIsNone(check_range("x", 5, 0, 10))
        self.assertIn("missing", check_range("x", None, 0, 10))
        self.assertIn("outside", check_range("x", 11, 0, 10))
        self.assertIn("not a number", check_range("x", "7", 0, 10))

    def test_is_number_rejects_bool_and_nan(self):
        self.assertFalse(is_number(True))
        self.assertFalse(is_number(float("nan")))
        self.assertTrue(is_number(3.5))

    def test_linear_slope(self):
        self.assertAlmostEqual(linear_slope([0, 1, 2, 3], [10, 8, 6, 4]), -2.0)
        self.assertEqual(linear_slope([1], [5]), 0.0)

    def test_compare_with_reference(self):
        result = compare_with_reference(90, 60)
        self.assertEqual(result["difference"], 30)
        self.assertEqual(result["percent_change"], 50.0)

    def test_split_start_and_end(self):
        start, end = split_start_and_end(list(range(12)))
        self.assertEqual(start, [0, 1, 2, 3])
        self.assertEqual(end, [8, 9, 10, 11])


class ParticipantTests(unittest.TestCase):
    def test_from_profile(self):
        participant = Participant.from_profile(PROFILE)
        self.assertEqual(participant.baseline_heart_rate, 70)
        self.assertEqual(participant.reference_values()["temperature"], 32.5)

    def test_setter_rejects_impossible_baseline(self):
        participant = Participant.from_profile(PROFILE)
        with self.assertRaises(ValueError):
            participant.baseline_heart_rate = 300
        self.assertEqual(participant.baseline_heart_rate, 70)  # unchanged

    def test_missing_profile_field(self):
        with self.assertRaises(ValueError):
            Participant.from_profile({"participant_id": "X"})


class ObservationTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(make_observation().is_usable)

    def test_missing_value_rejected(self):
        observation = make_observation(heart_rate=None)
        self.assertEqual(observation.status, Observation.REJECTED)

    def test_impossible_values_rejected(self):
        self.assertFalse(make_observation(heart_rate=265).is_usable)
        self.assertFalse(make_observation(activity_level=-0.2).is_usable)
        self.assertFalse(make_observation(temperature=50).is_usable)

    def test_missing_key_rejected(self):
        self.assertFalse(Observation.from_dict({"timestamp": 0, "heart_rate": 80}).is_usable)

    def test_low_quality_flagged(self):
        observation = make_observation(signal_quality=0.3)
        self.assertEqual(observation.status, Observation.FLAGGED)
        self.assertFalse(observation.is_usable)

    def test_problems_cannot_be_modified(self):
        observation = make_observation(heart_rate=None)
        self.assertIsInstance(observation.problems, tuple)


class SessionTests(unittest.TestCase):
    def test_composition_and_counts(self):
        observations = [make_observation(t) for t in range(5)]
        observations.append(make_observation(5, heart_rate=None))
        session = Session("S", Participant.from_profile(PROFILE), observations)
        counts = session.counts()
        self.assertEqual((counts["total"], counts["usable"], counts["rejected"]), (6, 5, 1))
        self.assertIsInstance(session.participant, Participant)

    def test_duplicate_timestamp_rejected(self):
        session = Session("S", Participant.from_profile(PROFILE),
                          [make_observation(1), make_observation(1)])
        self.assertEqual(session.counts()["rejected"], 1)

    def test_only_observation_objects_accepted(self):
        session = Session("S", Participant.from_profile(PROFILE))
        with self.assertRaises(TypeError):
            session.add_observation({"timestamp": 0})


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = SessionAnalyzer()

    def analyze(self, scenario, seed, windows=12):
        profile, observations = generate_fitness_data("P", scenario, seed, windows)
        return self.analyzer.analyze(Session.from_raw_data("S", profile, observations))

    def test_generated_scenarios_many_seeds(self):
        for scenario in available_scenarios():
            for seed in range(100):
                for windows in (6, 12, 24):
                    with self.subTest(scenario=scenario, seed=seed, windows=windows):
                        result = self.analyze(scenario, seed, windows)
                        self.assertEqual(result["classification"], EXPECTED_LABELS[scenario])

    def test_sample_scenarios(self):
        for scenario in get_all_scenarios():
            with self.subTest(scenario=scenario["name"]):
                session = Session.from_raw_data(scenario["name"], scenario["profile"],
                                                scenario["observations"])
                result = self.analyzer.analyze(session)
                self.assertEqual(result["classification"], scenario["expected"])

    def test_result_is_structured_dictionary(self):
        result = self.analyze("moderate_activity", 1)
        for key in ("classification", "explanation", "observation_counts", "summary",
                    "comparison_with_reference", "recovery", "excluded_observations"):
            self.assertIn(key, result)
        self.assertEqual(result["observation_counts"]["usable"], 12)

    def test_recovery_detected_only_in_recovery(self):
        self.assertTrue(self.analyze("recovery", 3)["recovery"]["detected"])
        self.assertFalse(self.analyze("high_activity", 3)["recovery"]["detected"])

    def test_empty_session(self):
        session = Session("empty", Participant.from_profile(PROFILE))
        result = self.analyzer.analyze(session)
        self.assertEqual(result["classification"], "insufficient data")

    def test_custom_rule_order_uses_overridden_methods(self):
        class AlwaysTestRule(ClassificationRule):
            label = "test label"

            def matches(self, evidence):
                return True

        result = SessionAnalyzer([AlwaysTestRule()]).analyze(
            Session("S", Participant.from_profile(PROFILE)))
        self.assertEqual(result["classification"], "test label")

    def test_base_rule_is_abstract(self):
        with self.assertRaises(NotImplementedError):
            ClassificationRule().matches({})

    def test_recovery_rule_thresholds(self):
        evidence = {"recovery": {"start_hr_increase": 50, "hr_drop": 30,
                                 "activity_drop": 0.5, "hr_slope": -3,
                                 "activity_slope": -0.05}}
        self.assertTrue(RecoveryRule().matches(evidence))
        evidence["recovery"]["hr_drop"] = 10
        self.assertFalse(RecoveryRule().matches(evidence))

    def test_report_contains_key_information(self):
        report = format_report(self.analyze("poor_quality", 1))
        self.assertIn("INSUFFICIENT DATA", report)
        self.assertIn("rejected", report)


if __name__ == "__main__":
    unittest.main(verbosity=1)
