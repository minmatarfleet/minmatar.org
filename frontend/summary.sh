echo "### Frontend test results" >> $GITHUB_STEP_SUMMARY
echo "Total tests... :eyeglasses:" >> $GITHUB_STEP_SUMMARY
jq '.numTotalTestSuites' artifacts/front-end-unit >> $GITHUB_STEP_SUMMARY