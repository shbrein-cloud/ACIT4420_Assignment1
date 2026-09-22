# Smart Fitness Session Analyzer

**Python Programming Assignment (I) – Option A: Smart Fitness Session Analyzer**

- **Student name:** _Sindre Hvesser Brein_
- **Student number:** _409906_

## Description

A fitness centre receives simulated measurements from wearable devices. This program
turns the raw dictionaries produced by the instructor-supplied generator into
objects, validates every observation window, summarises the usable measurements,
compares them with the participant's personal reference values, classifies the
session and explains the result in a readable console report.

A session is classified as one of: **resting**, **moderate activity**,
**high activity**, **recovering** or **insufficient data**. Every analysis is also
returned as a structured dictionary (printable as JSON with `--json`).

## Repository structure

```
.
|-- README.md
|-- main.py                  entry point: runs the scenarios and prints reports
|-- sample_data.py           the eight scenarios (5 generated + 3 hand-built)
|-- tests.py                 automated tests (unittest, standard library)
|-- requirements.txt         states that only the standard library is used
|-- data_generator.py        instructor-supplied generator (unmodified)
|-- example_usage.py         instructor-supplied example (unmodified)
`-- fitness_analyzer/       the application package
    |-- __init__.py
    |-- calculations.py      standalone calculation / validation / formatting functions
    |-- models.py            Participant, Observation, Session
    |-- rules.py             ClassificationRule and its five subclasses
    |-- analyzer.py          SessionAnalyzer
    `-- report.py            standalone presentation functions
```

The domain code was split into a package so that data classes, classification rules,
calculations and presentation can be read and tested separately.

## Installation and running

Requires Python 3.8 or newer. No packages need to be installed.

```bash
git clone https://github.com/shbrein-cloud/ACIT4420_Assignment1.git
cd REPOSITORY
python3 main.py
```

On systems where the command is `python` instead of `python3` (common on Windows),
use `python main.py` and `python tests.py`.

Optional commands:

```bash
python3 main.py --scenario recovery                           # one built-in scenario
python3 main.py --generate high_activity --seed 5 --windows 20  # a new generated session
python3 main.py --scenario resting --json                      # print the result dictionary
python3 tests.py                                               # run the tests
```

## Class design

| Class | Responsibility |
|---|---|
| `Participant` | Stores the participant id and personal reference values (heart rate, skin response, temperature). Rejects impossible baselines. |
| `Observation` | One measurement window. Validates itself on creation and ends up `valid`, `rejected` (missing / non-numeric / impossible value) or `flagged` (possible values but signal quality below 0.60). |
| `Session` | Groups one `Participant` and its `Observation` objects in time order, rejects duplicate timestamps, and provides usable values, counts and summaries. |
| `ClassificationRule` | Base class defining the rule interface: `matches(evidence)` and `explain(evidence)`. |
| `InsufficientDataRule`, `RecoveryRule`, `HighActivityRule`, `ModerateActivityRule`, `RestingRule` | One subclass per label; each overrides `matches` and `explain` and holds its own thresholds as class constants. |
| `SessionAnalyzer` | Holds an ordered list of rules, computes the evidence (reference comparison, recovery pattern), applies the first matching rule and returns the result dictionary. |

Standalone functions (`fitness_analyzer/calculations.py` and `report.py`):
`is_number`, `check_range`, `summarize`, `compare_with_reference`,
`linear_slope`, `split_start_and_end`, `format_value`, `format_signed`,
`format_summary_table`, `format_comparison`, `format_recovery`,
`format_excluded`, `format_report` and `format_overview`.

### Where the OOP concepts are demonstrated

- **Composition:** a `Session` *has a* `Participant` and *has* a list of
  `Observation` objects, and delegates validation to them. A `SessionAnalyzer`
  *has* a list of `ClassificationRule` objects. (`models.py`, `analyzer.py`)
- **Encapsulation:** `Participant` keeps its baselines in protected attributes
  (`_baseline_heart_rate`, ...) exposed through properties whose setters validate
  the new value; an invalid assignment raises `ValueError` and leaves the old value.
  `Observation` keeps `_values`, `_status` and `_problems` protected; `problems`
  returns an immutable tuple and the status can only change through `reject()`.
  `Session.observations` also returns a tuple so the list cannot be changed from outside.
- **Inheritance and overriding:** each rule subclass inherits from
  `ClassificationRule` and overrides `matches()`, `explain()` and
  `describe_thresholds()`. `SessionAnalyzer` only uses the base-class interface
  (polymorphism), so a new label can be added by writing a new subclass without
  changing the analyzer. Inheritance was *not* used for Participant/Session/Observation,
  because those are "has-a" relationships where composition fits better.
- **Class and static methods:** `Participant.from_profile()`,
  `Observation.from_dict()` and `Session.from_raw_data()` are class methods acting
  as alternative constructors from the generator's dictionaries.
  `SessionAnalyzer.default_rules()` is a static method returning the standard rule
  order, and `Participant._validated()` is a static helper that does not need
  object state.
- **Lists and dictionaries:** raw data arrives as a dictionary and a list of
  dictionaries; sessions store lists of observations; limits and summaries are
  dictionaries; the final result is a nested dictionary.

## Assumptions and validation rules

An observation is **rejected** if any field is missing, not a number, or outside
these possible ranges: timestamp non-negative integer, heart rate 35–205 bpm,
skin response 0–50, temperature 25–42 °C, activity 0–1, signal quality 0–1. A second
observation with an already used timestamp is also rejected. An otherwise valid
observation is **flagged** (and excluded) if signal quality is below **0.60**.
Only valid observations are used in summaries and classification.

## Classification rules

Rules are checked in this order; the first match gives the label. `HR increase`
means the session's average heart rate minus the participant's baseline heart rate,
and `activity` means average activity level.

1. **Insufficient data** – fewer than 6 usable observations, or fewer than 50% of
   the observations are usable.
2. **Recovering** – the first and last third of the usable windows (at least 2 each)
   are compared. All must hold: start heart rate at least 20 bpm above baseline
   (there was real effort); heart rate drops by at least 15 bpm *and* by at least 40%
   of the start elevation (it is returning toward baseline); activity drops by at
   least 0.20; the least-squares trends of both heart rate and activity are negative.
   Recovery is checked before intensity because a cool-down session has medium
   averages that would otherwise look like moderate activity.
3. **High activity** – HR increase ≥ 42 bpm **and** activity ≥ 0.65.
4. **Moderate activity** – HR increase ≥ 12 bpm **or** activity ≥ 0.30.
5. **Resting** – HR increase < 12 bpm and activity < 0.30.

Skin response and temperature are compared with the reference values and reported,
but are not used for classification because they change much less clearly than
heart rate and movement.

The thresholds were chosen from the ranges documented for the generator and then
checked: for each of the five generator scenarios, 2,000 seeds with 6, 12, 20 and 40
windows (40,000 sessions) were all classified as expected. `tests.py` repeats a
smaller version of this check (1,500 sessions).

## Scenarios

| Scenario | Source | Purpose |
|---|---|---|
| `resting` | generator, seed 11 | normal resting session |
| `moderate_activity` | generator, seed 42 | normal moderate exercise |
| `high_activity` | generator, seed 7 | normal intense exercise |
| `recovery` | generator, seed 42 | activity followed by recovery |
| `poor_quality` | generator, seed 3 | invalid sensor data |
| `partially_corrupted` | generator + manual damage | unusual: missing value, missing field, text value, low quality and a duplicate timestamp, but still enough good data |
| `too_few_observations` | generator + manual change | unusual: a short session whose usable windows fall below the minimum |
| `handwritten_cooldown` | written by hand | shows the program does not depend on the generator |

## Example output

Report for one session (`python3 main.py --scenario recovery`):

```
======================================================================
Scenario: recovery - Hard exercise followed by a cool-down.
Participant: P004   Session: recovery
======================================================================
CLASSIFICATION: RECOVERING
Reason: The session starts with elevated effort (heart rate 53.5 bpm above baseline) and then winds down: heart rate falls by 39.8 bpm and activity by 0.60 between the start and the end of the session. At the end the heart rate is 13.8 bpm above baseline.

Observations: 12 total, 12 usable, 0 rejected, 0 flagged (usable ratio 100%)
  None - all observations passed validation.

Summary of usable observations:
  Measurement       Count      Mean       Min       Max
  heart_rate           12    112.83        86       141
  skin_response        12      1.57      1.22      1.93
  temperature          12     33.05     32.81     33.34
  activity_level       12      0.48      0.10      0.88
  signal_quality       12      0.91      0.88      0.94

Comparison with personal reference values:
  heart_rate       reference       78   session   112.83   change +34.83 bpm (+44.7%)
  skin_response    reference     1.17   session     1.57   change +0.40 units (+34.2%)
  temperature      reference    32.76   session    33.05   change    +0.29 C (+0.9%)

Recovery analysis:
  Compared first and last 4 usable windows
  Heart rate: 131.5 -> 91.8 bpm (drop 39.8 bpm, trend -4.94 bpm/window)
  Activity drop: 0.60 (trend -0.072 per window)
  Recovery detected: yes

OVERVIEW
----------------------------------------------------------------------
Scenario                Expected            Classified          Usable
----------------------------------------------------------------------
recovery                recovering          recovering           12/12
----------------------------------------------------------------------
```

Overview printed at the end of `python3 main.py`:

```
----------------------------------------------------------------------
Scenario                Expected            Classified          Usable
----------------------------------------------------------------------
resting                 resting             resting              12/12
moderate_activity       moderate activity   moderate activity    12/12
high_activity           high activity       high activity        12/12
recovery                recovering          recovering           12/12
poor_quality            insufficient data   insufficient data     0/12
partially_corrupted     moderate activity   moderate activity     7/12
too_few_observations    insufficient data   insufficient data      4/6
handwritten_cooldown    recovering          recovering           10/10
----------------------------------------------------------------------
```

## Known limitations

- Thresholds are fixed rules tuned for the simulated data, not medically validated.
  They use the difference from the resting baseline and do not take age or maximum
  heart rate into account.
- A session gets exactly one label. A session that is mostly high activity with a
  short cool-down at the end, or that contains several intervals, is described by
  its dominant pattern only.
- Recovery detection compares only the first and last third of the session; a
  recovery that happens in the middle of a session is not detected.
- The signal-quality limit (0.60) and minimum of 6 usable observations are
  assumptions; very short sessions are always reported as insufficient data.
- The program processes one participant and one session at a time and does not
  store results between runs.
