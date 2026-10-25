"""The pure engine against real SDE data and real doctrine fits."""

from django.test import SimpleTestCase

from capabilities.engine.dogma import check_fit
from capabilities.engine.fit import parse_fit
from capabilities.engine.readiness import FitChecker, evaluate, train_next
from capabilities.engine.requirements import (
    Override,
    compute,
    hard_requirements,
)
from capabilities.tests.helpers import all_skills_at, fixture_eft, fixture_sde

SDE = fixture_sde()


def skill(name):
    tid = SDE.resolve(name)
    assert tid, name
    return tid


def requirements(name, roles=("primary",), **kwargs):
    fit = parse_fit(SDE, fixture_eft(name))
    return fit, compute(SDE, fit, roles=roles, **kwargs)


def levels(req, name):
    r = req.rows.get(skill(name))
    if r is None:
        return None
    return (
        max(r.required_level, r.fit_level),
        max(r.required_level, r.core_level),
        r.optimal_level,
    )


def core_names(req):
    return {
        r.name
        for r in req.rows.values()
        if r.required_level or r.core_level or r.fit_level
    }


class GoldenChecksTest(SimpleTestCase):
    """The checks from the design doc, without the empirical raise."""

    def test_revelation(self):
        _, req = requirements("revelation")
        self.assertEqual(req.capability, "Dreads")
        names = core_names(req)
        for wanted in (
            "Jump Drive Calibration",
            "Capital Energy Turret",
            "Surgical Strike",
            "Rapid Firing",
            "Controlled Bursts",
            "EM Armor Compensation",
            "Thermal Armor Compensation",
            "Kinetic Armor Compensation",
            "Explosive Armor Compensation",
            "Long Range Targeting",
            "Signature Analysis",
            "Amarr Dreadnought",
        ):
            self.assertIn(wanted, names)
        for name in names:
            self.assertNotIn("Drone Specialization", name)
            self.assertNotIn("Shield", name)

    def test_napoc(self):
        _, req = requirements("napoc")
        self.assertEqual(req.capability, "DPS")
        names = core_names(req)
        for wanted in (
            "Large Energy Turret",
            "Surgical Strike",
            "Rapid Firing",
            "Controlled Bursts",
            "Motion Prediction",
            "Trajectory Analysis",
            "Sharpshooter",
            "Navigation",
            "Evasive Maneuvering",
        ):
            self.assertIn(wanted, names)
        self.assertFalse([n for n in names if n.startswith("Jump")])

    def test_napoc_utility_drones_are_optional(self):
        _, req = requirements("napoc")
        drones = req.rows[skill("Minmatar Drone Specialization")]
        self.assertEqual(drones.tier, "optimal")
        self.assertEqual(drones.reason, "utility drones")

    def test_guardian(self):
        _, req = requirements("guardian")
        self.assertEqual(req.capability, "Logistics")
        names = core_names(req)
        for wanted in (
            "Logistics Cruisers",
            "Remote Armor Repair Systems",
            "Capacitor Management",
            "Capacitor Systems Operation",
        ):
            self.assertIn(wanted, names)
        # Warrior IIs on a Guardian are kit: it is not a drone boat.
        self.assertNotIn("Minmatar Drone Specialization", names)

    def test_damnation(self):
        _, req = requirements("damnation", roles=("support",))
        self.assertEqual(req.capability, "Links")
        names = core_names(req)
        for wanted in (
            "Armored Command",
            "Skirmish Command",
            "Information Command",
            "Armored Command Specialist",
            "Information Command Specialist",
            "Command Burst Specialist",
            "Command Ships",
        ):
            self.assertIn(wanted, names)

    def test_tackle_punisher_drops_gunnery_support_from_core(self):
        _, req = requirements("tackle_punisher", roles=("secondary",))
        self.assertEqual(req.capability, "Tackle")
        self.assertEqual(req.rows[skill("Surgical Strike")].tier, "optimal")


class FitCheckTest(SimpleTestCase):
    def test_every_fixture_fit_fits_with_all_skills_at_five(self):
        for name in (
            "revelation",
            "napoc",
            "guardian",
            "damnation",
            "tackle_punisher",
            "links_brutix_navy",
        ):
            fit = parse_fit(SDE, fixture_eft(name))
            result = check_fit(SDE, fit.fit_items(), all_skills_at(SDE, 5))
            self.assertTrue(result.fits, (name, result))

    def test_napoc_cpu_matches_cpu_management(self):
        fit = parse_fit(SDE, fixture_eft("napoc"))
        base = SDE.attrs(fit.hull)[48]
        result = check_fit(SDE, fit.fit_items(), all_skills_at(SDE, 5))
        self.assertAlmostEqual(result.cpu_output, base * 1.25)

    def test_hard_requirements_alone_do_not_fit_the_napoc(self):
        fit = parse_fit(SDE, fixture_eft("napoc"))
        hard = hard_requirements(SDE, [fit.hull] + fit.items())
        result = check_fit(SDE, fit.fit_items(), hard)
        self.assertIn("cpu", result.problems)

    def test_fit_plan_levels_make_it_fit(self):
        fit, req = requirements("napoc")
        hard = hard_requirements(SDE, [fit.hull] + fit.items())
        plan = {s: r.fit_level for s, r in req.rows.items() if r.fit_level}
        self.assertTrue(plan)
        skills = {
            **hard,
            **{s: max(hard.get(s, 0), lv) for s, lv in plan.items()},
        }
        self.assertTrue(check_fit(SDE, fit.fit_items(), skills).fits)

    def test_rig_drawback_skill_counts(self):
        """Hybrid Metastasis Adjusters raise railgun grid; the rigging skill offsets it."""
        fit = parse_fit(SDE, fixture_eft("links_brutix_navy"))
        skills = all_skills_at(SDE, 5)
        skills[skill("Hybrid Weapon Rigging")] = 0
        result = check_fit(SDE, fit.fit_items(), skills)
        self.assertIn("power", result.problems)

    def test_offline_modules_use_no_cpu(self):
        fit = parse_fit(SDE, fixture_eft("damnation"))
        online = check_fit(SDE, fit.fit_items(), all_skills_at(SDE, 5))
        fit.modules = [(t, True, c) for t, _, c in fit.modules]
        everything = check_fit(SDE, fit.fit_items(), all_skills_at(SDE, 5))
        self.assertGreater(everything.cpu_used, online.cpu_used)


class ReadinessTest(SimpleTestCase):
    def _evaluate(self, name, skills, **kwargs):
        fit, req = requirements(name, **kwargs)
        checker = FitChecker(SDE, fit, req)
        hull = SDE.with_prerequisites(SDE.required_skills(fit.hull))
        return req, evaluate(SDE, req, checker, hull, skills)

    def test_all_fives_are_core_ready(self):
        _, r = self._evaluate("guardian", all_skills_at(SDE, 5))
        self.assertTrue(r.unlocked and r.hard_ready and r.core_ready)
        self.assertEqual(r.support_score, 100)

    def test_no_skills_is_not_unlocked(self):
        _, r = self._evaluate("guardian", {})
        self.assertFalse(r.unlocked)
        self.assertFalse(r.hard_ready)

    def test_hard_only_pilot_can_not_fit_it(self):
        fit = parse_fit(SDE, fixture_eft("guardian"))
        hard = hard_requirements(SDE, [fit.hull] + fit.items())
        req, r = self._evaluate("guardian", hard)
        self.assertTrue(r.unlocked)
        self.assertFalse(r.hard_ready)
        self.assertTrue(r.fit_problems)
        self.assertGreater(r.days_to_hard, 0)
        self.assertTrue(train_next(SDE, req, hard))

    def test_missing_core_skill_is_hard_ready_not_core_ready(self):
        skills = all_skills_at(SDE, 5)
        skills[skill("Capacitor Management")] = 0
        _, r = self._evaluate("guardian", skills)
        self.assertTrue(r.hard_ready)
        self.assertFalse(r.core_ready)
        self.assertEqual(r.missing_core[0][0], skill("Capacitor Management"))


class CoreAboveRequiredTest(SimpleTestCase):
    def test_core_level_above_a_required_level_still_gates(self):
        """Revelation: Amarr Dreadnought I to fly it, higher for core."""
        fit, req = requirements("revelation")
        ad = skill("Amarr Dreadnought")
        row = req.rows[ad]
        self.assertLess(row.required_level, row.core_level)
        skills = all_skills_at(SDE, 5)
        skills[ad] = row.required_level
        checker = FitChecker(SDE, fit, req)
        hull = SDE.with_prerequisites(SDE.required_skills(fit.hull))
        result = evaluate(SDE, req, checker, hull, skills)
        self.assertTrue(result.hard_ready)
        self.assertFalse(result.core_ready)
        self.assertEqual(
            result.missing_core, [[ad, row.required_level, row.core_level]]
        )


class OverrideAndSubstitutionTest(SimpleTestCase):
    def test_exclude_removes_a_row(self):
        target = skill("Signature Analysis")
        _, req = requirements(
            "revelation",
            overrides=[Override(skill=target, action="exclude", tier="core")],
        )
        self.assertNotIn(target, req.rows)

    def test_set_level_wins_and_is_marked(self):
        target = skill("Jump Drive Calibration")
        _, req = requirements(
            "revelation",
            overrides=[
                Override(
                    skill=target, action="set_level", tier="core", level=5
                )
            ],
        )
        row = req.rows[target]
        self.assertEqual(row.core_level, 5)
        self.assertEqual(row.sources["core"], ["override"])
        self.assertTrue(row.overridden)

    def test_a_substitute_module_satisfies_its_slot(self):
        fit = parse_fit(SDE, fixture_eft("guardian"))
        t2 = SDE.resolve("Large Remote Armor Repairer II")
        t1 = SDE.resolve("Large Remote Armor Repairer I")
        _, req = requirements("guardian", substitutes={t2: [t1]})
        self.assertIn(t2, req.alternatives)
        # A pilot who can use only the T1 still passes the item requirements.
        skills = all_skills_at(SDE, 5)
        skills[skill("Remote Armor Repair Systems")] = 4
        checker = FitChecker(SDE, fit, req)
        hull = SDE.with_prerequisites(SDE.required_skills(fit.hull))
        result = evaluate(SDE, req, checker, hull, skills)
        self.assertFalse(
            [
                m
                for m in result.missing_required
                if m[0] == skill("Remote Armor Repair Systems")
            ]
        )


class EmpiricalTest(SimpleTestCase):
    def test_raise_to_what_ninety_percent_of_proven_pilots_have(self):
        target = skill("Jump Drive Calibration")
        pilots = []
        for _ in range(10):
            p = all_skills_at(SDE, 5)
            pilots.append(p)
        _, req = requirements("revelation", proven_skills=pilots)
        self.assertEqual(req.rows[target].core_level, 5)
        self.assertIn("empirical", req.rows[target].sources["core"])
        self.assertEqual(req.proven_pilots, 10)
        self.assertEqual(req.proven_pass_rate, 1.0)

    def test_too_few_pilots_change_nothing(self):
        target = skill("Jump Drive Calibration")
        _, base = requirements("revelation")
        _, req = requirements(
            "revelation", proven_skills=[all_skills_at(SDE, 5)] * 3
        )
        self.assertEqual(
            req.rows[target].core_level, base.rows[target].core_level
        )
