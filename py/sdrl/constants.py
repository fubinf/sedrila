AUTHOR_ALTDIR_PREFIX = "ALT:"
AUTHOR_ITREEDIR_PREFIX = "ITREE:"
AUTHOR_CONFIG_FILENAME = "sedrila.yaml"  # at top-level of source dir
AUTHOR_GLOSSARY_BASENAME = "glossary"  # .md at top-level of chapterdir, .html in build directory
AUTHOR_OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR = "instructor"
CACHE_FILENAME = ".sedrila_cache"  # author: in instructor target dir
EDITOR_CMD_DEFAULT = "/usr/bin/nano"
EVENTCACHE_FILENAME = ".sedrila_events"  # evaluator: in respos_dir
HTML_DIFFICULTY_SIGN = "&#x26ab;&#xfe0e;"  # &#x26ab; is an icon and always black, &#xfe0e; is the text-variant selector
  # https://commons.wikimedia.org/wiki/Unicode_circle_shaped_symbols
HTACCESS_FILE = ".htaccess"  # in instructor part of build directory
METADATA_FILE = "course.json"  # at top-level of build directory
PARTICIPANT_FILE = "student.yaml"
PARTICIPANTSLIST_FILE = "participants.gpg"
PATHSET_FILE_EXT = "files" # extension of ".files" meta files
SUBMISSION_FILE = "submission.yaml"
SUBMISSION_COMMIT_MSG = "submission.yaml"
SUBMISSION_CHECKED_COMMIT_MSG = "submission.yaml checked"
# These are for fresh submission / checked submission / resulting task status:
# (beware when renaming: there are same-named CSS styles)
SUBMISSION_CHECK_MARK = "CHECK"  # please check / not checked / -- 
SUBMISSION_NONCHECK_MARK = "NONCHECK"  # do not check / -- / never checked
SUBMISSION_ACCEPT_MARK = "ACCEPT"  # -- / accepted / accepted
SUBMISSION_REJECT_MARK = "REJECT"  # -- / rejected / rejected forever
SUBMISSION_REJECTOID_MARK = "REJECTOID"  # -- / -- / rejected but can be submitted again
SUBMISSION_OVERRIDE_PREFIX = "OVERRIDE_"
SUBMISSION_NONTASK_MARK = "NO_SUCH_TASKNAME"
SUBMISSION_STATE_FRESH = "FRESH"  # last commit indicates new submission
SUBMISSION_STATE_CHECKING = "CHECKING"  # SUBMISSION_FILE modified, but not commited
SUBMISSION_STATE_CHECKED = "CHECKED"  # last commit indicates checked submission
SUBMISSION_STATE_OTHER = "OTHER"  # none of the above
SEDRILA_COMMAND_ENV = "SEDRILA_COMMAND"
