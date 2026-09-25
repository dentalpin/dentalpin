# staff_attendance — overview

Clock in/out events for clinic staff, current-state lookup, and a
daily pairing report (in→out seconds per member, open shifts flagged).

Events are append-only: corrections happen via a later opposite punch,
never rewrite. Shifts, rosters, overtime math, payroll linkage, and
absence flags are explicitly later work with their own design.
