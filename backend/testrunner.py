import logging

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
        return (
            self.module < other.module and self.test_method < other.test_method
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

        self.report_results()
        
        return result

    def report_results(self):
        """Report the results of the test suite"""

        results.sort()

        module_width, method_width = self.calc_col_widths()
        total_width = module_width + method_width + 9
        
        print('=' * total_width)
        print(f"{'MODULE':{module_width}} {'TEST':{method_width}} RESULT")
        print('-' * total_width)
        for result in results:
            print(
                f"{result.module:{module_width}} {result.test_method:{method_width}} {result.status}"
            )
        print('=' * total_width)

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
