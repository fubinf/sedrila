# sedrila CHANGELOG

Version 0.5.0 alpha (2024-02-24)
- near-complete functionality for `author`
- very basic functionality for `student` and `instructor`

Version 0.6.0 alpha (2024-03-26)
- `author --cache` added to greatly speed up the processing of small changes
- `author` now leaves empty taskgroups and chapters out from TOCs
- `author` added linkslists of subsequent (assumed by, required by) tasks at bottom of task pages
- `author` generates .htaccess file in instructor website
- `student --init`: generate `student.yaml` from interactive prompts 
- `student --submission`: interactive task selection dialog 
- `instructor`: interactive task accept/reject dialog

Version 0.7.0 alpha (2024-04-02)
- `author`: add [FOLDOUT] macro
- `instructor`: improvements of interactive mode
- `instructor`: instructor subdirectory now simply named "instructor"
- change from `_sedrila.yaml` to `sedrila.yaml` in the generated website
- introduce naming conventions for chapters, taskgroups, tasks

Version 0.8.0 alpha (upcoming) 
- removed support for 'profiles' metadatum in tasks; it is superfluous
- `author`: ZIP files no longer contain inner path parts chapter/taskgroup/task/ 
- ...
