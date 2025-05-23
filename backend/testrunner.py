import logging
import os

from django.test.runner import DiscoverRunner
from unittest import TextTestRunner, TextTestResult, TestCase

log = logging.getLogger(__name__)

results = []


class IndividualResult:
    """Represents the result of a single test scenario"""

    def __init__(self, test: TestCase, status: str):
        self.test_method = test._testMethodName.removeprefix("test_")
        self.module = self.module_name(test.__module__)
        self.status = status

    def module_name(self, module: str) -> str:
        """Returns a short version of a module name"""
        s = module.removeprefix("backend.")
        n = s.find(".")
        if n >= 0:
            return s[0:n]
        else:
            return s

    def __str__(self):
        return f"{self.module} > {self.test_method} ({self.status})"

    def __lt__(self, other):
        return self.module < other.module or (
            self.module == other.module
            and self.test_method < other.test_method
        )


class CustomTestResult(TextTestResult):
    """Custom test result handler"""

    def addSuccess(self, test):
        super().addSuccess(test)
        results.append(IndividualResult(test, "Success"))

    def addError(self, test, err):
        super().addError(test, err)
        results.append(IndividualResult(test, "Error"))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        results.append(IndividualResult(test, "Failure"))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        results.append(IndividualResult(test, "Skipped"))


class InnerRunner(TextTestRunner):
    """Inner runner called by main TestRunner"""

    def run(self, test):
        self.resultclass = CustomTestResult
        result = super().run(test)
        return result


class Runner(DiscoverRunner):
    """
    A custom test runner that reports more structured results

    The standard Django test runner doesn't provide a full
    summary of all the tests that were run at the end, so this
    TestRunner adds that.

    Use the `--test-runner` parameter to enable it.

    `python ./manage.py test --testrunner="testrunner.Runner"`

    The Django runner is itself a wrapper around an internal
    runner, so this class does the same so that minimal changes
    are needed.
    """

    test_runner = InnerRunner

    def run_tests(self, test_labels, **kwargs):
        """Override parent to report results afterwards"""

        log.info("Using custom TestRunner...")
        result = super().run_tests(test_labels, **kwargs)

        with open("testresults.txt", mode="w", encoding="utf-8") as f:
            self.report_results(f)

        print("Test results written to testsresults.txt")

        self.write_markdown_job_summary()

        return result

    # pylint: disable=W1405

    def report_results(self, f):
        """Report the results of the test suite"""

        results.sort()

        module_width, method_width = self.calc_col_widths()
        total_width = module_width + method_width + 9

        print("=" * total_width, file=f)
        print(
            f"{'MODULE':{module_width}} {'TEST':{method_width}} RESULT", file=f
        )
        print("-" * total_width, file=f)

        success_count = 0

        for result in results:
            print(
                f"{result.module:{module_width}} {result.test_method:{method_width}} {result.status}",
                file=f,
            )
            if result.status == "Success":
                success_count += 1

        print("-" * total_width, file=f)
        print(f"{success_count} out of {len(results)} tests passed.", file=f)
        print("=" * total_width, file=f)

    def calc_col_widths(self):
        """Calculate the widths of the columns to display"""
        module_width = 0
        method_width = 0

        for result in results:
            module_width = max(module_width, len(result.module))
            method_width = max(method_width, len(result.test_method))

        module_width += 2
        method_width += 2
        return module_width, method_width

    def write_markdown_job_summary(self):
        output_file = os.environ.get("GITHUB_STEP_SUMMARY")
        if not output_file:
            print("GITHUB_STEP_SUMMARY not set, not writing summary")

        success_count = 0
        fail_count = 0
        error_count = 0

        for result in results:
            if result.status == "Success":
                success_count += 1
            if result.status == "Error":
                error_count += 1
            if result.status == "Failure":
                fail_count += 1

        with open(output_file, mode="w", encoding="utf-8") as f:
            print("### Backend test results", file=f)
            print(
                "| Pass :white_check_mark: | Fail :red_circle: | Error :large_orange_diamond: | Total :large_blue_circle: |",
                file=f,
            )
            print("| ---- | ---- | ----- | ----- |", file=f)
            print(
                f"| {success_count} | {fail_count} | {error_count} | {len(results)} |",
                file=f,
            )

        print("Markdown summary written to", output_file)
