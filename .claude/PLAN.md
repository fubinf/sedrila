Regarding `expand_macros()` in `macros.py:119-139`, a user reported this:

<!-- sedrila: macros off -->`bool isNotPrime[ARRAY_SIZE];`<!-- sedrila: macros off end -->
führt leider dazu, dass zwar die Fehlermeldung weg ist, aber jedes Makro nach dem End-Tag nicht geparst wird.
<!-- sedrila: macros off -->`bool isNotPrime[ARRAY_SIZE];`
<!-- sedrila: macros off end -->
oder
<!-- sedrila: macros off -->
`bool isNotPrime[ARRAY_SIZE];`<!-- sedrila: macros off end -->
oder
<!-- sedrila: macros off -->
`bool isNotPrime[ARRAY_SIZE];`
<!-- sedrila: macros off end -->
hingegen funktioniert wie erwartet.

- adapt `macros_test.py:30-49` to check for this problem
- if the test then fails, find and explain the bug;
- fix the bug.
