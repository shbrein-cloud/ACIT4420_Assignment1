"""SessionAnalyzer: turns a Session into a structured result dictionary."""

import statistics

from .calculations import compare_with_reference, linear_slope, split_start_and_end
from .models import Session
from .rules import (ClassificationRule, HighActivityRule, InsufficientDataRule,
                    ModerateActivityRule, RecoveryRule, RestingRule)


class SessionAnalyzer:
    """Analyzes sessions using an ordered list of ClassificationRule objects.

    The analyzer has rules. Rules are tried in order and the
    first one that matches decides the label, so the order expresses priority:
    data quality first, then the time pattern, then overall
    intensity from highest to lowest.
    """

    def __init__(self, rules=None):
        rules = list(rules) if rules is not None else self.default_rules()
        if not rules:
            raise ValueError("At least one classification rule is required")
        for rule in rules:
            if not isinstance(rule, ClassificationRule):
                raise TypeError("rules must be ClassificationRule objects")
        self._rules = rules

    @staticmethod
    def default_rules():
        """The standard rule order used by the fitness centre."""
        return [InsufficientDataRule(), RecoveryRule(), HighActivityRule(),
                ModerateActivityRule(), RestingRule()]

    @property
    def rules(self):
        return tuple(self._rules)

    def analyze(self, session):
        """Analyze a Session and return the result as a dictionary."""
        if not isinstance(session, Session):
            raise TypeError("analyze() expects a Session object")

        counts = session.counts()
        summary = session.summary()
        comparison = self._compare_with_reference(session, summary)
        recovery = self._recovery_pattern(session)

        evidence = dict(counts)
        evidence["recovery"] = recovery
        evidence["hr_increase"] = comparison["heart_rate"]["difference"]
        evidence["mean_activity"] = summary["activity_level"]["mean"]

        label, explanation = self._classify(evidence)
        if label != InsufficientDataRule.label and counts["rejected"] + counts["flagged"]:
            explanation += " {} observation(s) were excluded before analysis.".format(
                counts["rejected"] + counts["flagged"])

        return {
            "session_id": session.session_id,
            "participant_id": session.participant.participant_id,
            "classification": label,
            "explanation": explanation,
            "observation_counts": counts,
            "excluded_observations": [
                {"timestamp": o.timestamp, "status": o.status, "problems": list(o.problems)}
                for o in session.observations if not o.is_usable
            ],
            "summary": summary,
            "comparison_with_reference": comparison,
            "recovery": recovery,
        }

    def _classify(self, evidence):
        for rule in self._rules:
            if rule.matches(evidence):
                return rule.label, rule.explain(evidence)
        return "unclassified", "No classification rule matched this session."

    @staticmethod
    def _compare_with_reference(session, summary):
        references = session.participant.reference_values()
        return {name: compare_with_reference(summary[name]["mean"], reference)
                for name, reference in references.items()}

    @staticmethod
    def _recovery_pattern(session):
        """Compare the start and the end of the session to detect recovery."""
        usable = session.usable_observations()
        baseline = session.participant.baseline_heart_rate
        start, end = split_start_and_end(usable)
        if not start or not end:
            return {"detected": False, "segment_size": 0, "start_hr": None,
                    "end_hr": None, "start_hr_increase": 0.0, "end_hr_increase": 0.0,
                    "hr_drop": 0.0, "activity_drop": 0.0, "hr_slope": 0.0,
                    "activity_slope": 0.0}

        start_hr = statistics.fmean(o.heart_rate for o in start)
        end_hr = statistics.fmean(o.heart_rate for o in end)
        start_activity = statistics.fmean(o.activity_level for o in start)
        end_activity = statistics.fmean(o.activity_level for o in end)
        times = [o.timestamp for o in usable]

        result = {
            "segment_size": len(start),
            "start_hr": round(start_hr, 1),
            "end_hr": round(end_hr, 1),
            "start_hr_increase": round(start_hr - baseline, 1),
            "end_hr_increase": round(end_hr - baseline, 1),
            "hr_drop": round(start_hr - end_hr, 1),
            "activity_drop": round(start_activity - end_activity, 2),
            "hr_slope": round(linear_slope(times, [o.heart_rate for o in usable]), 2),
            "activity_slope": round(
                linear_slope(times, [o.activity_level for o in usable]), 3),
        }
        result["detected"] = RecoveryRule().matches({"recovery": result})
        return result
