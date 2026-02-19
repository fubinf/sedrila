Currently, bracketed expressions in program code in tasks can be mistaken for macro calls:
`myarray[MYCONSTANT]` makes sedrila think a macro named `MYCONSTANT` is to be called.
This macro does not exist, triggering a misleading, false-positve "undefined macro" error message.

We want to get rid of this behavior.

The right solution would be to exclude all backquoted content from macro expansion.
However, since sedrila does not use a proper Markdown parser, rather mostly only a simplistic scanner,
this is not easy to accomplish.

So we resort to the following crude-but-effective approach:
Task authors must bracket any code block containing one or more pseudo-macrocalls in marker comments like so
(imagine triple quotes around the code block; markers can be inside or outside those triple quotes):
```
<!-- sedrila: macros off -->
(more code here)
myarray[MYCONSTANT] = 42
(still more code here)
<!-- sedrila: macros off end -->
```

We apply the following logic to `expand_macros` in `macros.py`.
- `macros_off_regexp` and `macros_om_regexp` are the block markers.
- When we expand macros, we find any stretch `block` of `markup` between block markers.
- we leave the block markers in, store `block` in a list `blocks` of blocks, and remove `block` from `markup`
- we perform macro expansion on the remainder of `markup`
- we find the `len(blocks)` pairs of block markers and replace each by the corresponding block,
  so that the end result consists of unchanged blocks, macro-expanded other markup, and no block markers.

Make this change to `expand_macros` now.
Then add a test of this new functionality in `macros_test.py`. 
The test should have _two_ non-expanded blocks, not only one.
Then amend the documentation: Insert a new section 2.9 "Preventing macro expansion" into `authors.md`
that shortly describes the problem and the solution along the lines as above (but with
visible triple quotes; we are using the Python Markdown module).

Ask if anything is unclear about the above plan.
When all is clear, execute it.
