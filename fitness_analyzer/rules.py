"""Classification rules.

Each rule is a small class that answers two questions about the session
evidence (a dictionary produced by SessionAnalyzer):

* ``matches(evidence)`` - does this label describe the session?
* ``explain(evidence)`` - why (in plain language)?

All rules share the same interface through the ClassificationRule base class
and override these two methods. The analyzer only talks to the base-class
interface, so adding a new label means adding a new subclass - the analyzer
itself does not change.
"""

from .calculations import format_value


class ClassificationRule:
    """Base class for one session label."""

    label = "unclassified"

    def matches(self, evidence):
        raise NotImplementedError("Subclasses must implement matches()")

    def explain(self, evidence):
        return "The session was labelled '{}'.".format(self.label)

    def describe_thresholds(self):
        """Short human-readable description of the rule, for documentation."""
        return self.label

    def __repr__(self):
        return "{}(label={!r})".format(type(self).__name__, self.label)


class InsufficientDataRule(ClassificationRule):
    label = "insufficient data"
    MIN_USABLE_OBSERVATIONS = 6
    MIN_USABLE_RATIO = 0.5

    def matches(self, evidence):
        return (evidence["usable"] < self.MIN_USABLE_OBSERVATIONS
                or evidence["usable_ratio"] < self.MIN_USABLE_RATIO)

    def explain(self, evidence):
        return ("Only {} of {} observations ({:.0%}) were usable. At least {} usable "
                "observations and {:.0%} of the session are needed for a reliable "
                "classification.").format(
                    evidence["usable"], evidence["total"], evidence["usable_ratio"],
                    self.MIN_USABLE_OBSERVATIONS, self.MIN_USABLE_RATIO)

    def describe_thresholds(self):
        return "fewer than {} usable observations, or under {:.0%} usable".format(
            self.MIN_USABLE_OBSERVATIONS, self.MIN_USABLE_RATIO)


class RecoveryRule(ClassificationRule):
    """Activity at the start, then heart rate and movement decline at the end."""

    label = "recovering"
    MIN_START_HR_INCREASE = 20    # bpm above baseline at the start
    MIN_HR_DROP = 15              # bpm, start segment mean minus end segment mean
    MIN_ACTIVITY_DROP = 0.20      # activity units
    MIN_RETURN_FRACTION = 0.40    # share of the start elevation that must be recovered

    def matches(self, evidence):
        recovery = evidence["recovery"]
        return (recovery["start_hr_increase"] >= self.MIN_START_HR_INCREASE
                and recovery["hr_drop"] >= self.MIN_HR_DROP
                and recovery["activity_drop"] >= self.MIN_ACTIVITY_DROP
                and recovery["hr_drop"]
                >= self.MIN_RETURN_FRACTION * recovery["start_hr_increase"]
                and recovery["hr_slope"] < 0
                and recovery["activity_slope"] < 0)

    def explain(self, evidence):
        r = evidence["recovery"]
        return ("The session starts with elevated effort (heart rate {} bpm above "
                "baseline) and then winds down: heart rate falls by {} bpm and "
                "activity by {} between the start and the end of the session. "
                "At the end the heart rate is {} bpm above baseline.").format(
                    format_value(r["start_hr_increase"], 1), format_value(r["hr_drop"], 1),
                    format_value(r["activity_drop"], 2),
                    format_value(r["end_hr_increase"], 1))

    def describe_thresholds(self):
        return ("start HR >= baseline + {} bpm, HR drop >= {} bpm and >= {:.0%} of "
                "the start elevation, activity drop >= {}, both trends negative").format(
                    self.MIN_START_HR_INCREASE, self.MIN_HR_DROP,
                    self.MIN_RETURN_FRACTION, self.MIN_ACTIVITY_DROP)


class HighActivityRule(ClassificationRule):
    label = "high activity"
    MIN_HR_INCREASE = 42     # bpm above baseline
    MIN_ACTIVITY = 0.65

    def matches(self, evidence):
        return (evidence["hr_increase"] >= self.MIN_HR_INCREASE
                and evidence["mean_activity"] >= self.MIN_ACTIVITY)

    def explain(self, evidence):
        return ("Average heart rate is {} bpm above the personal baseline "
                "(threshold {}) and average activity is {} (threshold {}).").format(
                    format_value(evidence["hr_increase"], 1), self.MIN_HR_INCREASE,
                    format_value(evidence["mean_activity"], 2), self.MIN_ACTIVITY)

    def describe_thresholds(self):
        return "HR >= baseline + {} bpm AND activity >= {}".format(
            self.MIN_HR_INCREASE, self.MIN_ACTIVITY)


class ModerateActivityRule(ClassificationRule):
    label = "moderate activity"
    MIN_HR_INCREASE = 12
    MIN_ACTIVITY = 0.30

    def matches(self, evidence):
        return (evidence["hr_increase"] >= self.MIN_HR_INCREASE
                or evidence["mean_activity"] >= self.MIN_ACTIVITY)

    def explain(self, evidence):
        return ("Average heart rate is {} bpm above baseline and average activity "
                "is {}. At least one exceeds the moderate threshold ({} bpm / {}) "
                "but the high-activity thresholds are not both reached.").format(
                    format_value(evidence["hr_increase"], 1),
                    format_value(evidence["mean_activity"], 2),
                    self.MIN_HR_INCREASE, self.MIN_ACTIVITY)

    def describe_thresholds(self):
        return "HR >= baseline + {} bpm OR activity >= {}".format(
            self.MIN_HR_INCREASE, self.MIN_ACTIVITY)


class RestingRule(ClassificationRule):
    label = "resting"
    MAX_HR_INCREASE = ModerateActivityRule.MIN_HR_INCREASE
    MAX_ACTIVITY = ModerateActivityRule.MIN_ACTIVITY

    def matches(self, evidence):
        return (evidence["hr_increase"] < self.MAX_HR_INCREASE
                and evidence["mean_activity"] < self.MAX_ACTIVITY)

    def explain(self, evidence):
        return ("Average heart rate stays close to the personal baseline ({} bpm "
                "difference, limit {}) and movement is low (activity {}, limit "
                "{}).").format(
                    format_value(evidence["hr_increase"], 1), self.MAX_HR_INCREASE,
                    format_value(evidence["mean_activity"], 2), self.MAX_ACTIVITY)

    def describe_thresholds(self):
        return "HR < baseline + {} bpm AND activity < {}".format(
            self.MAX_HR_INCREASE, self.MAX_ACTIVITY)
